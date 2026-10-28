"""No camera/model/network/database/alert dependencies: synthetic stream tests."""
import asyncio
from contextlib import suppress
import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend.websocket.live import LatestFrameStream, send_latest
from backend.test_ppe_defaults import BACKEND, fresh_config, load_source


async def until(predicate):
    async def wait():
        while not predicate():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(wait(), 2)


class FakeCapture:
    def __init__(self, opened=True):
        self.opened = opened
        self.frames = queue.Queue()
        self.released = threading.Event()

    def isOpened(self):
        return self.opened

    def read(self):
        frame = self.frames.get(timeout=2)
        return frame is not None, frame

    def release(self):
        self.released.set()


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.incoming = asyncio.Queue()

    async def send_json(self, packet):
        self.sent.append(packet)

    async def receive_json(self):
        message = await self.incoming.get()
        if isinstance(message, Exception):
            raise message
        return message


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.streams = []

    async def asyncTearDown(self):
        for stream, cap in self.streams:
            cap.frames.put(None)  # Unblock fake read so the owner can release it.
            await stream.close()
            self.assertTrue(cap.released.is_set())
            self.assertFalse(stream._reader.is_alive())

    def stream(self, analyze=lambda frame: frame, interval=3, opened=True, on_result=None):
        cap = FakeCapture(opened)
        stream = LatestFrameStream(lambda: cap, analyze, interval, on_result).start()
        self.streams.append((stream, cap))
        return stream, cap

    async def test_default_interval_is_three_and_configurable(self):
        self.assertEqual(fresh_config().settings.STREAM_DETECTION_INTERVAL, 3)
        self.assertEqual(fresh_config({"STREAM_DETECTION_INTERVAL": "5"}).settings.STREAM_DETECTION_INTERVAL, 5)
        self.assertEqual(fresh_config({"STREAM_DETECTION_INTERVAL": "0"}).settings.STREAM_DETECTION_INTERVAL, 1)

    async def test_detection_skips_frames_and_reuses_result(self):
        calls, recorded = [], []

        def analyze(frame):
            calls.append(frame)
            return f"boxes:{frame}"

        async def record(frame, result):
            recorded.append((frame, result))

        stream, cap = self.stream(analyze, on_result=record)
        cap.frames.put(1)
        await until(lambda: stream.result == 'boxes:1')
        for frame in (2, 3):
            cap.frames.put(frame)
            await until(lambda: stream.sequence == frame)
            await asyncio.sleep(0.02)
            self.assertEqual(stream.latest(), (frame, frame, 'boxes:1'))
            self.assertEqual(calls, [1])
        cap.frames.put(4)
        await until(lambda: stream.result == 'boxes:4')
        self.assertEqual(calls, [1, 4])
        self.assertEqual(recorded, [(1, 'boxes:1'), (4, 'boxes:4')])

    async def test_slow_inference_drops_old_inputs_and_capture_keeps_moving(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def analyze(frame):
            calls.append(frame)
            if frame == 1:
                entered.set()
                release.wait(timeout=2)
            return frame

        stream, cap = self.stream(analyze)
        self.addCleanup(release.set)
        cap.frames.put(1)
        await until(entered.is_set)
        for frame in range(2, 11):
            cap.frames.put(frame)
        await until(lambda: stream.sequence == 10)
        self.assertEqual(stream.latest(), (10, 10, None))
        release.set()
        await until(lambda: stream.result == 10)
        self.assertEqual(calls, [1, 10])

    async def test_unavailable_camera_reports_error_and_releases(self):
        stream, cap = self.stream(opened=False)
        await until(lambda: stream.error)
        self.assertIn('cannot open camera', stream.error)
        self.assertEqual(stream.sequence, 0)
        await until(cap.released.is_set)

    async def test_failed_read_reports_error_instead_of_frozen_frame(self):
        stream, cap = self.stream()
        cap.frames.put(1)
        await until(lambda: stream.sequence == 1)
        cap.frames.put(None)
        await until(lambda: stream.error)
        self.assertIn('stopped returning frames', stream.error)

    async def test_inference_error_is_visible(self):
        def broken(frame):
            raise ValueError('synthetic failure')
        stream, cap = self.stream(broken)
        cap.frames.put(1)
        await until(lambda: stream.error)
        self.assertIn('processing failed', stream.error)
        self.assertNotIn('synthetic failure', stream.error)

    async def test_slow_viewer_has_one_frame_in_flight_then_gets_latest(self):
        socket = FakeSocket()
        state = [1, 'frame1', 'cached boxes']
        stream = SimpleNamespace(error=None, latest=lambda: tuple(state))
        task = asyncio.create_task(send_latest(socket, stream, lambda f, r: {"frame": f, "boxes": r}))
        try:
            await until(lambda: len(socket.sent) == 1)
            state[:] = [30, 'frame30', 'cached boxes']
            await asyncio.sleep(0.03)
            self.assertEqual(len(socket.sent), 1)
            await socket.incoming.put({"type": "frame_ack", "frame_id": 999})
            await asyncio.sleep(0.02)
            self.assertEqual(len(socket.sent), 1)
            await socket.incoming.put({"type": "frame_ack", "frame_id": 1})
            await until(lambda: len(socket.sent) == 2)
            self.assertEqual(socket.sent[-1], {"frame": "frame30", "boxes": "cached boxes", "frame_id": 30})
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def test_disconnect_detected_before_any_camera_frame(self):
        socket = FakeSocket()
        stream = SimpleNamespace(error=None, latest=lambda: (0, None, None))
        await socket.incoming.put(ConnectionError('closed'))
        with self.assertRaisesRegex(ConnectionError, 'closed'):
            await asyncio.wait_for(send_latest(socket, stream, lambda f, r: {}), 1)

    async def test_no_display_ack_times_out_instead_of_queueing(self):
        socket = FakeSocket()
        stream = SimpleNamespace(error=None, latest=lambda: (1, 'frame', None))
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            await send_latest(socket, stream, lambda f, r: {}, timeout=0.03)
        self.assertEqual(len(socket.sent), 1)


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the real endpoint wiring with every external side effect replaced."""
    def setUp(self):
        import sys
        self.db = Mock()
        self.camera = SimpleNamespace(id=1, name='Synthetic', enabled=True)
        self.db.query.return_value.filter.return_value.first.return_value = self.camera
        self.detector = Mock()
        self.annotate = Mock(side_effect=lambda frame, detections, violations: frame)
        modules = {
            'cv2': SimpleNamespace(IMWRITE_JPEG_QUALITY=1, imencode=Mock(return_value=(True, b'synthetic-jpeg'))),
            'alerts.alert_manager': SimpleNamespace(trigger_alerts=Mock()),
            'api.upload': SimpleNamespace(_serialize_detections=lambda detections: detections),
            'config': SimpleNamespace(settings=SimpleNamespace(STREAM_DETECTION_INTERVAL=3)),
            'db.database': SimpleNamespace(SessionLocal=lambda: self.db),
            'db.models': SimpleNamespace(Camera=Mock(), Violation=Mock(), WorkerObservation=Mock()),
            'detection.annotator': SimpleNamespace(annotate_frame=self.annotate),
            'detection.deduplicator': SimpleNamespace(deduplicator=Mock()),
            'detection.model': SimpleNamespace(get_detector=self.detector),
            'detection.violation_logic': SimpleNamespace(compute_violations=Mock()),
        }
        with patch.dict(sys.modules, modules):
            self.api = load_source('backend.websocket.isolated_manager', BACKEND / 'websocket' / 'manager.py')
        self.socket = FakeSocket()
        self.socket.accept = unittest.mock.AsyncMock()
        self.socket.close = unittest.mock.AsyncMock()
        self.api.record_observation = Mock()
        self.original_writer = self.api._write_violations
        self.api._write_violations = Mock(side_effect=AssertionError('No DB writes allowed'))
        self.api._dispatch_alerts = Mock(side_effect=AssertionError('No alerts allowed'))

    async def check_closed(self, code):
        await asyncio.wait_for(self.api.websocket_endpoint(self.socket, 1), 2)
        self.socket.close.assert_awaited_once_with(code=code)
        self.assertNotIn(self.socket, self.api.manager.active_connections)
        self.api._write_violations.assert_not_called()
        self.api._dispatch_alerts.assert_not_called()
        self.db.close.assert_called_once()

    async def test_missing_or_disabled_camera_cleans_up_connection(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        await self.check_closed(4404)
        self.assertIn('not found', self.socket.sent[0]['error'])
        self.detector.assert_not_called()

    async def test_disabled_camera_never_opens_capture(self):
        self.camera.enabled = False
        await self.check_closed(4403)
        self.assertIn('disabled', self.socket.sent[0]['error'])
        self.detector.assert_not_called()

    async def test_model_failure_sends_error_and_cleans_up_connection(self):
        self.detector.side_effect = RuntimeError('Synthetic model unavailable')
        await self.check_closed(4400)
        self.assertIn('processing failed', self.socket.sent[0]['error'])
        self.assertNotIn('Synthetic model unavailable', self.socket.sent[0]['error'])

    async def test_camera_open_failure_sends_error_and_releases_capture(self):
        cap = FakeCapture(opened=False)
        self.api._build_capture = Mock(return_value=cap)
        await self.check_closed(4400)
        self.assertIn('cannot open camera', self.socket.sent[0]['error'])
        self.assertTrue(cap.released.is_set())

    async def test_failed_camera_read_sends_error_instead_of_blank_success(self):
        cap = FakeCapture()
        cap.frames.put(None)
        self.api._build_capture = Mock(return_value=cap)
        await self.check_closed(4400)
        self.assertIn('stopped returning frames', self.socket.sent[0]['error'])
        self.assertTrue(cap.released.is_set())

    def test_packet_uses_latest_frame_with_cached_results_and_no_fake_initial_stats(self):
        import numpy as np
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        self.assertIsNone(self.api._stream_packet(self.camera, frame, None)['stats'])
        worker = {'person_bbox': [1, 1, 15, 15], 'missing_ppe': [], 'status': 'COMPLIANT'}
        packet = self.api._stream_packet(self.camera, frame, ([], [worker]))
        self.assertEqual(packet['stats'], {'persons': 1, 'compliant': 1, 'violations': 0, 'compliance_rate': 100.0, 'mask_not_assessable': 0})
        np.testing.assert_array_equal(self.annotate.call_args.args[0], frame)
        self.assertEqual(self.annotate.call_args.args[2], [worker])
        self.api._write_violations.assert_not_called()
        self.api._dispatch_alerts.assert_not_called()

    def test_unknown_mask_is_not_compliant_and_never_logged_as_violation(self):
        import numpy as np
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        worker = {'person_bbox': [0, 0, 15, 15], 'missing_ppe': [], 'status': 'NOT_ASSESSABLE', 'mask_assessment': 'not assessable'}
        packet = self.api._stream_packet(self.camera, frame, ([], [worker]))
        self.assertEqual(packet['stats']['compliant'], 0)
        self.assertEqual(packet['stats']['violations'], 0)
        self.assertEqual(packet['stats']['mask_not_assessable'], 1)
        self.assertIsNone(packet['stats']['compliance_rate'])
        self.assertEqual(packet['workers'], [worker])
        self.assertEqual(self.original_writer(self.camera, frame, [], [worker]), (0, []))
        self.db.add.assert_not_called()
        self.db.commit.assert_called_once()
        self.api.trigger_alerts.assert_not_called()


if __name__ == '__main__':
    unittest.main()
