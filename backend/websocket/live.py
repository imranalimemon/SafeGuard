"""Latest-frame capture and sampled inference, independent of API/DB/alerts."""
import asyncio
from contextlib import suppress
import threading


class LatestFrameStream:
    def __init__(self, open_capture, analyze, interval=3, on_result=None):
        self.open_capture = open_capture
        self.analyze = analyze
        self.interval = max(1, interval)
        self.on_result = on_result
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
        except Exception as exc:
            reason = str(exc) if str(exc) in {"cannot open camera", "camera stopped returning frames"} else "capture failed"
            self.error = f"Camera not available: {reason}"
        finally:
            if cap is not None:
                cap.release()

    def latest(self):
        with self._lock:
            return self.sequence, self.frame, self.result

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
                result = await asyncio.to_thread(self.analyze, frame)
                if self._stop.is_set():
                    return
                with self._lock:
                    self.result = result
                if self.on_result is not None:
                    await self.on_result(frame, result)
        except Exception as exc:
            self.error = "Camera processing failed. Check the system log."

    async def close(self):
        self._stop.set()
        if self._inference is not None:
            self._inference.cancel()
            with suppress(asyncio.CancelledError):
                await self._inference
        # The capture thread owns release(), avoiding release/read races.
        await asyncio.to_thread(self._reader.join, 1.0)


async def send_latest(websocket, stream, make_packet, timeout=5):
    """One frame in flight; after display acknowledgement, select newest input."""
    last_sent = 0
    pending = None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    receive = asyncio.create_task(websocket.receive_json())
    try:
        while True:
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
            sequence, frame, result = stream.latest()
            if pending is None and frame is not None and sequence != last_sent:
                packet = await asyncio.to_thread(make_packet, frame, result)
                packet["frame_id"] = sequence
                await websocket.send_json(packet)
                last_sent = pending = sequence
                deadline = loop.time() + timeout
            await asyncio.sleep(0.005)
    finally:
        receive.cancel()
        with suppress(asyncio.CancelledError):
            await receive
