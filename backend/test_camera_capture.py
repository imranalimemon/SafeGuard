"""Capture API tests with mocks only: no devices, network, DB or alerts."""
import asyncio
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend.detection import camera_capture
from backend.test_ppe_defaults import BACKEND, load_source


class CameraCaptureTests(unittest.TestCase):
    def test_network_capture_has_open_and_read_deadlines(self):
        camera = SimpleNamespace(source_type='ip', url='http://localhost/video', username=None, password=None)
        with patch.object(camera_capture.cv2, 'VideoCapture') as factory:
            camera_capture.open_capture(camera)
        factory.assert_called_once_with(camera.url, camera_capture.cv2.CAP_FFMPEG, [
            camera_capture.cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
            camera_capture.cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])

    def test_webcam_uses_device_backend_not_network_parameters(self):
        camera = SimpleNamespace(source_type='webcam', url='2')
        with patch.object(camera_capture.cv2, 'VideoCapture') as factory, patch.object(camera_capture.sys, 'platform', 'win32'):
            camera_capture.open_capture(camera)
        factory.assert_called_once_with(2, camera_capture.cv2.CAP_DSHOW)

    def test_test_camera_requires_decoded_frame_and_releases_capture(self):
        database, models = ModuleType('db.database'), ModuleType('db.models')
        database.get_db = lambda: None
        models.Camera = object
        with patch.dict(sys.modules, {'db.database': database, 'db.models': models}):
            api = load_source('isolated_camera_capture_api', BACKEND / 'api/cameras.py')
        package = ModuleType('detection'); package.__path__ = []
        with patch.dict(sys.modules, {'detection': package, 'detection.camera_capture': camera_capture}):
            for ok, frame, expected in [(False, None, False), (True, None, False), (True, object(), True)]:
                capture = Mock()
                capture.isOpened.return_value = True
                capture.read.return_value = (ok, frame)
                with patch.object(camera_capture, 'open_capture', return_value=capture):
                    result = asyncio.run(api._try_open(SimpleNamespace(name='fixture')))
                self.assertEqual(result['ok'], expected)
                capture.release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
