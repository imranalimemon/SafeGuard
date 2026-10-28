"""Latest-frame capture and sampled inference, independent of API/DB/alerts."""
import asyncio
from contextlib import suppress
import threading
import time
import logging

logger = logging.getLogger("safeguard.stream")


class LatestFrameStream:
    def __init__(self, open_capture, analyze, interval=3, on_result=None, reconnect_attempts=0, backoff=1.0):
        self.open_capture = open_capture
        self.analyze = analyze
        self.interval = max(1, interval)
        self.on_result = on_result
        self.reconnect_attempts = reconnect_attempts
        self.backoff = backoff
        self.status = "connecting"
        self.captured_at = None
        self.epoch = 0
        self.sequence = 0
        self.frame = None
        self.result = None
        self.error = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reader = threading.Thread(target=self._capture, daemon=True)
        self._inference = None

    def start(self):
        self._reader.start()
        self._inference = asyncio.create_task(self._detect())
        return self

    def _capture(self):
        failures = 0
        while not self._stop.is_set():
            cap = None
            try:
                cap = self.open_capture()
                if not cap.isOpened():
                    raise RuntimeError("cannot open camera")
                while not self._stop.is_set():
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        raise RuntimeError("camera stopped returning frames")
                    with self._lock:
                        self.sequence += 1
                        self.frame = frame
                        self.captured_at = time.monotonic()
                        self.status = "streaming"
            except Exception as exc:
                reason = str(exc) if str(exc) in {"cannot open camera", "camera stopped returning frames"} else "capture failed"
                with self._lock:
                    self.frame = self.result = None
                    self.epoch += 1
                if self._stop.is_set():
                    break
                if failures >= self.reconnect_attempts:
                    self.error = f"Camera not available: {reason}"
                    self.status = "failed"
                    logger.warning('%s', self.error)
                    break
                failures += 1
                self.status = f"reconnecting ({failures}/{self.reconnect_attempts})"
                logger.warning('Camera %s: %s', self.status, reason)
            finally:
                if cap is not None:
                    cap.release()
            # Interruptible wait, bounded attempts for this stream session.
            if self._stop.wait(min(8.0, self.backoff * 2 ** (failures - 1))):
                break

    def latest(self):
        with self._lock:
            return self.sequence, self.frame, self.result

    def snapshot(self):
        with self._lock:
            return self.sequence, self.frame, self.result, self.captured_at

    async def _detect(self):
        last = None
        try:
            while not self._stop.is_set() and not self.error:
                sequence, frame, _ = self.latest()
                if frame is None or (last is not None and sequence - last < self.interval):
                    await asyncio.sleep(0.005)
                    continue
                # Always take the latest eligible frame; never queue missed frames.
                last = sequence
                epoch = self.epoch
                result = await asyncio.to_thread(self.analyze, frame)
                if self._stop.is_set():
                    return
                if epoch != self.epoch:
                    continue
                with self._lock:
                    if self.frame is not None:
                        self.result = result
                if self.on_result is not None:
                    await self.on_result(frame, result)
        except Exception as exc:
            logger.error("Camera inference failed (%s)", type(exc).__name__)
            self.error = "Camera processing failed. Check the system log."

    async def close(self):
        self._stop.set()
        if self._inference is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._inference), timeout=10)
            except asyncio.TimeoutError:
                self._inference.cancel()
                logger.warning('Inference worker exceeded shutdown deadline.')
            except asyncio.CancelledError:
                pass
        # The capture owner releases the handle after its bounded network read.
        await asyncio.to_thread(self._reader.join, 3.5)
        if self._reader.is_alive():
            logger.warning('Capture driver did not stop within shutdown deadline.')
        self.status = "stopped"


async def send_latest(websocket, stream, make_packet, timeout=5, authorized=None):
    """One frame in flight; after display acknowledgement, select newest input."""
    last_check = 0
    last_status = 0
    last_sent = 0
    pending = None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    receive = asyncio.create_task(websocket.receive_json())
    try:
        while True:
            if authorized is not None and loop.time() - last_check >= 1:
                last_check = loop.time()
                if not await authorized():
                    raise RuntimeError("Session expired. Sign in again.")
            status = getattr(stream, 'status', '')
            if status.startswith('reconnecting') and loop.time() - last_status >= 1:
                await websocket.send_json({'status': status, 'message': 'Camera not available; reconnecting.'})
                last_status = loop.time()
                deadline = loop.time() + timeout
                pending = None
            if receive.done():
                ack = receive.result()  # Propagate disconnect, even before first frame.
                receive = asyncio.create_task(websocket.receive_json())
                if ack.get("type") == "frame_ack" and ack.get("frame_id") == pending:
                    pending = None
                    deadline = loop.time() + timeout
            if stream.error:
                raise RuntimeError(stream.error)
            if loop.time() > deadline:
                raise RuntimeError("Camera not available: frame delivery timed out")
            if hasattr(stream, 'snapshot'):
                sequence, frame, result, captured_at = stream.snapshot()
            else:
                sequence, frame, result = stream.latest()
                captured_at = None
            if pending is None and frame is not None and sequence != last_sent:
                packet = await asyncio.to_thread(make_packet, frame, result)
                packet["frame_id"] = sequence
                if captured_at is not None:
                    packet['frame_age_ms'] = (time.monotonic() - captured_at) * 1000
                await websocket.send_json(packet)
                last_sent = pending = sequence
                deadline = loop.time() + timeout
            await asyncio.sleep(0.005)
    finally:
        receive.cancel()
        with suppress(asyncio.CancelledError):
            await receive
