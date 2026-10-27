"""Upload routes with temporary storage, in-memory DB, fake detector/capture/alerts."""
import asyncio
import io
import inspect
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session  # Keep ORM registries loaded outside module-isolation patches.
from fastapi import BackgroundTasks, HTTPException, UploadFile
from starlette.datastructures import Headers
from starlette.concurrency import run_in_threadpool
from backend.test_ppe_defaults import BACKEND, fresh_config, load_source

MP4_HEADER = b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42'
AVI_HEADER = b'RIFF\x10\x00\x00\x00AVI '


class FakeCapture:
    def __init__(self, frames, opened=True):
        self.frames = list(frames); self.index = 0; self.opened = opened; self.released = False

    def isOpened(self): return self.opened
    def get(self, key): return len(self.frames)
    def read(self):
        if self.index >= len(self.frames): return False, None
        frame = self.frames[self.index]; self.index += 1
        return True, frame
    def release(self): self.released = True


def worker(status='VIOLATION', missing=None, mask='detected'):
    missing = ['Helmet'] if missing is None else missing
    return {'person_bbox': [1, 1, 15, 15], 'has_ppe': ['Safety Vest', 'Face Mask'],
            'missing_ppe': missing, 'mask_assessment': mask, 'not_assessable': [],
            'status': status, 'confidence': 0.9, 'compliance_score': 0.67}


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = fresh_config()
        self.config.settings.DATABASE_URL = 'sqlite:///' + (self.root / 'test.db').as_posix()
        self.config.settings.SCREENSHOT_DIR = str(self.root / 'screenshots')
        (self.root / 'screenshots').mkdir()
        self.frame = np.zeros((16, 16, 3), dtype=np.uint8)
        self.cap = FakeCapture([self.frame] * 7)
        self.cv = SimpleNamespace(imread=Mock(return_value=self.frame),
            imwrite=Mock(side_effect=self.write_image), CAP_PROP_FRAME_COUNT=7,
            VideoCapture=Mock(side_effect=lambda path: self.cap))
        self.detect = Mock(return_value=[{'class_id': 2, 'class_name': 'Person', 'bbox': [1, 1, 15, 15], 'confidence': 0.9}])
        self.rules = Mock(side_effect=lambda detections, frame: [worker()])
        self.alerts = Mock(side_effect=AssertionError('No alerts allowed'))
        self.dedup = Mock(); self.dedup.should_log.return_value = True
        package = ModuleType('db'); package.__path__ = [str(BACKEND / 'db')]
        modules = {'config': self.config, 'db': package, 'cv2': self.cv,
            'detection.model': SimpleNamespace(get_detector=lambda: SimpleNamespace(detect=self.detect)),
            'detection.violation_logic': SimpleNamespace(compute_violations=self.rules),
            'detection.annotator': SimpleNamespace(annotate_frame=lambda frame, det, rules: frame),
            'detection.deduplicator': SimpleNamespace(deduplicator=self.dedup),
            'alerts.alert_manager': SimpleNamespace(trigger_alerts=self.alerts)}
        with patch.dict(sys.modules, modules):
            self.database = load_source('db.database', BACKEND / 'db/database.py')
            sys.modules['db.database'] = self.database
            self.models = load_source('db.models', BACKEND / 'db/models.py')
            sys.modules['db.models'] = self.models
            self.api = load_source('isolated_upload_api', BACKEND / 'api/upload.py')
        self.database.Base.metadata.create_all(self.database.engine)
        self.addCleanup(self.database.engine.dispose)
        self.db = self.database.SessionLocal(); self.addCleanup(self.db.close)
        self.tasks = BackgroundTasks()
        self.folders = []
        self.original_temp = tempfile.TemporaryDirectory

    def write_image(self, filename, frame):
        Path(filename).write_bytes(b'annotated-test-output')
        return True

    def upload(self, content=None, filename='worker.png', mime='image/png'):
        if content is None:
            stream = io.BytesIO(); Image.new('RGB', (16, 16)).save(stream, format='PNG'); content = stream.getvalue()
        return UploadFile(filename=filename, file=io.BytesIO(content), headers=Headers({'content-type': mime}))

    def call(self, upload, video=False):
        def folder(**kwargs):
            value = self.original_temp(dir=self.root, **kwargs); self.folders.append(Path(value.name)); return value
        try:
            with patch.object(self.api.tempfile, 'TemporaryDirectory', side_effect=folder):
                return (self.api.upload_video if video else self.api.upload_image)(self.tasks, upload, self.db)
        finally:
            self.assertTrue(upload.file.closed)
            self.assertTrue(all(not p.exists() for p in self.folders))
            self.alerts.assert_not_called()

    def test_image_returns_annotation_workers_ppe_and_created_record_ids(self):
        result = self.call(self.upload(filename='../../worker.png'))
        self.assertEqual(result['media_type'], 'image')
        self.assertEqual(result['workers'][0]['ppe_status'], {'Helmet': 'missing', 'Safety Vest': 'present', 'Face Mask': 'present'})
        self.assertEqual(result['stats']['total_persons'], 1)
        self.assertEqual(result['created_violations'][0]['id'], self.db.query(self.models.Violation).one().id)
        self.assertEqual(result['created_violations'][0]['source'], 'image_upload')
        self.assertTrue((self.root / 'screenshots' / Path(result['annotated_image_url']).name).is_file())
        self.assertIs(self.rules.call_args.kwargs['frame'], self.frame)
        self.assertEqual(len(self.tasks.tasks), 1)  # Scheduled fake only; never executed.

    def test_mask_unknown_creates_no_record_or_alert(self):
        row = worker('NOT_ASSESSABLE', missing=[], mask='not assessable'); row['has_ppe'] = ['Helmet', 'Safety Vest']
        self.rules.side_effect = lambda detections, frame: [row]
        result = self.call(self.upload())
        self.assertEqual(result['workers'][0]['ppe_status']['Face Mask'], 'mask not assessable')
        self.assertEqual(result['created_violations'], [])
        self.assertEqual(result['violations'], [])
        self.assertEqual(self.db.query(self.models.Violation).count(), 0)
        self.assertEqual(self.tasks.tasks, [])

    def test_video_real_summary_schema_and_downloadable_key_frames(self):
        result = self.call(self.upload(MP4_HEADER, 'workers.mp4', 'video/mp4'), video=True)
        self.assertEqual(result['total_frames'], 7)
        self.assertEqual(result['frames_processed'], 3)
        self.assertEqual(result['worker_observations'], 3)
        self.assertEqual(result['max_workers_in_frame'], 1)
        self.assertEqual(result['violations_logged'], 3)
        self.assertTrue(all(row['source'] == 'video_upload' for row in result['created_violations']))
        self.assertEqual(len(result['violation_frames']), 3)
        self.assertTrue(1 <= len(result['key_frames']) <= 6)
        for frame in result['key_frames']:
            self.assertTrue((self.root / 'screenshots' / Path(frame['screenshot_url']).name).exists())
        self.assertTrue(self.cap.released)

    def test_short_video_still_analyzes_first_frame(self):
        self.cap = FakeCapture([self.frame])
        result = self.call(self.upload(MP4_HEADER, 'short.mov', 'video/quicktime'), video=True)
        self.assertEqual(result['frames_processed'], 1)

    def test_cooldown_count_matches_actual_records(self):
        self.dedup.should_log.return_value = False
        result = self.call(self.upload())
        self.assertEqual(result['stats']['suppressed_by_cooldown'], 1)
        self.assertEqual(result['created_violations'], [])

    def test_bad_extension_mime_empty_content_and_corrupt_image_are_errors(self):
        for content, name, mime, status in [
            (b'a', 'file.exe', 'application/octet-stream', 415),
            (b'a', 'file.png', 'image/jpeg', 415),
            (b'', 'file.png', 'image/png', 400),
            (b'corrupt', 'file.png', 'image/png', 415),
        ]:
            with self.subTest(name=name, status=status), self.assertRaises(HTTPException) as error:
                self.call(self.upload(content, name, mime))
            self.assertEqual(error.exception.status_code, status)
        self.detect.assert_not_called()

    def test_oversize_partial_copy_is_cleaned(self):
        self.config.settings.MAX_IMAGE_UPLOAD_BYTES = 10
        with self.assertRaises(HTTPException) as error:
            self.call(self.upload(b'x' * 11))
        self.assertEqual(error.exception.status_code, 413)
        self.detect.assert_not_called()

    def test_decoded_image_dimensions_are_bounded(self):
        self.config.settings.MAX_IMAGE_PIXELS = 10
        with self.assertRaises(HTTPException) as error:
            self.call(self.upload())
        self.assertEqual(error.exception.status_code, 413)

    def test_wrong_actual_image_format_cannot_bypass_extension_check(self):
        stream = io.BytesIO(); Image.new('RGB', (16, 16)).save(stream, format='GIF')
        with self.assertRaises(HTTPException) as error:
            self.call(self.upload(stream.getvalue()))
        self.assertEqual(error.exception.status_code, 415)

    def test_detector_and_output_failures_clean_temp_files(self):
        self.detect.side_effect = RuntimeError('synthetic inference failure')
        with self.assertLogs(self.api.__name__, level='ERROR'), self.assertRaises(HTTPException) as error:
            self.call(self.upload())
        self.assertEqual(error.exception.status_code, 500)
        self.detect.side_effect = None
        self.cv.imwrite.side_effect = None; self.cv.imwrite.return_value = False
        with self.assertLogs(self.api.__name__, level='ERROR'), self.assertRaises(HTTPException):
            self.call(self.upload())
        self.assertEqual(list((self.root / 'screenshots').iterdir()), [])

    def test_database_failure_removes_only_new_uncommitted_output(self):
        existing = self.root / 'screenshots' / 'existing.jpg'; existing.write_bytes(b'keep')
        with patch.object(self.db, 'commit', side_effect=RuntimeError('synthetic DB failure')), self.assertLogs(self.api.__name__, level='ERROR'), self.assertRaises(HTTPException):
            self.call(self.upload())
        self.assertEqual(list((self.root / 'screenshots').iterdir()), [existing])

    def test_video_failure_releases_capture_and_preserves_committed_evidence(self):
        self.detect.side_effect = [self.detect.return_value, RuntimeError('synthetic failure')]
        with self.assertLogs(self.api.__name__, level='ERROR'), self.assertRaises(HTTPException):
            self.call(self.upload(AVI_HEADER, 'fail.avi', 'video/x-msvideo'), video=True)
        self.assertTrue(self.cap.released)
        self.assertEqual(self.db.query(self.models.Violation).count(), 1)
        self.assertEqual(len(list((self.root / 'screenshots').iterdir())), 1)

    def test_unopenable_and_empty_videos_release_resources(self):
        for opened in (False, True):
            self.cap = FakeCapture([], opened=opened)
            with self.assertRaises(HTTPException) as error:
                self.call(self.upload(MP4_HEADER, 'bad.mp4', 'video/mp4'), video=True)
            self.assertEqual(error.exception.status_code, 415)
            self.assertTrue(self.cap.released)

    def test_disguised_non_video_content_is_rejected_before_decoder(self):
        with self.assertRaises(HTTPException) as error:
            self.call(self.upload(b'#EXTM3U\nhttps://example.invalid/video', 'fake.mp4', 'video/mp4'), video=True)
        self.assertEqual(error.exception.status_code, 415)
        self.cv.VideoCapture.assert_not_called()

    def test_concurrent_upload_gets_clear_busy_error(self):
        self.api._upload_slot.acquire()
        try:
            with self.assertRaises(HTTPException) as error:
                self.call(self.upload())
            self.assertEqual(error.exception.status_code, 429)
        finally:
            self.api._upload_slot.release()


class UploadResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_upload_handler_is_offloaded_while_event_loop_keeps_ticking(self):
        # The real FastAPI worker dispatch used for sync route handlers.
        source = (BACKEND / 'api/upload.py').read_text(encoding='utf-8')
        self.assertIn('def upload_video(', source)
        self.assertNotIn('async def upload_video(', source)
        self.assertNotIn('async def upload_image(', source)
        ticks = []
        async def ticker():
            while not ticks or ticks[-1] < 4:
                ticks.append(len(ticks))
                await asyncio.sleep(0.005)
        await asyncio.gather(run_in_threadpool(time.sleep, 0.06), ticker())
        self.assertGreaterEqual(len(ticks), 5)

    async def test_real_image_route_does_not_block_event_loop_during_slow_inference(self):
        fixture = UploadTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        entered, release = threading.Event(), threading.Event()
        detections = fixture.detect.return_value
        def slow(frame):
            entered.set(); release.wait(timeout=2)
            return detections
        fixture.detect.side_effect = slow
        upload = fixture.upload()
        task = asyncio.create_task(run_in_threadpool(fixture.api.upload_image, fixture.tasks, upload, fixture.db))
        try:
            async def started():
                while not entered.is_set(): await asyncio.sleep(0.005)
            await asyncio.wait_for(started(), 1)
            for _ in range(4): await asyncio.sleep(0.005)
            self.assertFalse(task.done())
        finally:
            release.set()
        result = await asyncio.wait_for(task, 2)
        self.assertEqual(result['media_type'], 'image')
        self.assertTrue(upload.file.closed)
        fixture.alerts.assert_not_called()


if __name__ == '__main__':
    unittest.main()
