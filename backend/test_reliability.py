"""Reliability tests use fake captures/runtime and temporary log storage."""
import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from backend.detection.providers import create_session
from backend.logging_setup import RedactingFormatter, configure_logging, tail_logs
from backend.websocket.live import LatestFrameStream, send_latest
from backend.test_live_stream import FakeCapture, FakeSocket, until


class ProviderTests(unittest.TestCase):
    def runtime(self, available):
        return SimpleNamespace(get_available_providers=lambda: available,
            SessionOptions=lambda: SimpleNamespace(), ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL='sequential'),
            InferenceSession=Mock(return_value=object()))

    def test_cpu_only(self):
        runtime = self.runtime(['CPUExecutionProvider'])
        create_session(runtime, 'fake.onnx')
        self.assertEqual(runtime.InferenceSession.call_args.kwargs['providers'], ['CPUExecutionProvider'])

    def test_directml_options_and_cpu_fallback(self):
        runtime = self.runtime(['DmlExecutionProvider', 'CPUExecutionProvider'])
        runtime.InferenceSession.side_effect = [RuntimeError('accelerator unavailable'), 'cpu']
        self.assertEqual(create_session(runtime, 'fake.onnx'), 'cpu')
        first = runtime.InferenceSession.call_args_list[0].kwargs
        self.assertEqual(first['providers'], ['DmlExecutionProvider', 'CPUExecutionProvider'])
        self.assertFalse(first['sess_options'].enable_mem_pattern)
        self.assertEqual(runtime.InferenceSession.call_args.kwargs['providers'], ['CPUExecutionProvider'])

    def test_logging_rotation_tail_and_secret_redaction(self):
        with tempfile.TemporaryDirectory() as folder:
            config = SimpleNamespace(LOG_DIR=folder, ALERT_DELIVERY_MODE='preview', SMTP_PASSWORD='private-secret')
            handler = configure_logging(config)
            try:
                handler.maxBytes = 300
                log = logging.getLogger('safeguard.test')
                for i in range(30):
                    log.warning('fixture %s private-secret rtsp://user:pass@camera/stream?token=secret', i)
                lines = tail_logs(folder, 3)
                self.assertLessEqual(len(lines), 3)
                self.assertTrue(list(Path(folder).glob('safeguard.log.*')))
                for file in Path(folder).glob('safeguard.log*'):
                    self.assertNotIn('private-secret', file.read_text())
                    self.assertNotIn('user:pass', file.read_text())
                    self.assertNotIn('token=secret', file.read_text())
            finally:
                logging.getLogger().removeHandler(handler)
                handler.close()


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_then_recovers_and_other_camera_keeps_running(self):
        bad, good, other = FakeCapture(False), FakeCapture(), FakeCapture()
        attempts = iter([bad, good])
        stream = LatestFrameStream(lambda: next(attempts), lambda x: x, reconnect_attempts=1, backoff=.01).start()
        independent = LatestFrameStream(lambda: other, lambda x: x).start()
        try:
            other.frames.put('other'); good.frames.put('recovered')
            await until(lambda: stream.result == 'recovered' and independent.result == 'other')
            self.assertEqual(stream.status, 'streaming')
            self.assertTrue(bad.released.is_set())
            self.assertIsNone(independent.error)
        finally:
            good.frames.put(None); other.frames.put(None)
            await stream.close(); await independent.close()
            self.assertFalse(stream._reader.is_alive())

    async def test_retry_budget_and_close_interrupts_backoff(self):
        factory = Mock(side_effect=lambda: FakeCapture(False))
        stream = LatestFrameStream(factory, lambda x: x, reconnect_attempts=2, backoff=.01).start()
        await until(lambda: stream.error)
        await stream.close()
        self.assertEqual(factory.call_count, 3)
        stream = LatestFrameStream(lambda: FakeCapture(False), lambda x: x, reconnect_attempts=3, backoff=8).start()
        await until(lambda: stream.status.startswith('reconnecting'))
        await asyncio.wait_for(stream.close(), 1)
        self.assertFalse(stream._reader.is_alive())

    async def test_session_revocation_stops_delivery(self):
        socket = FakeSocket()
        stream = SimpleNamespace(error=None, latest=lambda: (0, None, None))
        async def denied(): return False
        with self.assertRaisesRegex(RuntimeError, 'Session expired'):
            await send_latest(socket, stream, lambda f, r: {}, authorized=denied)
        self.assertEqual(socket.sent, [])


if __name__ == '__main__': unittest.main()
