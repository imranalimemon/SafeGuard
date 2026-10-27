"""Synthetic worker boxes and injected visibility: no model/camera/DB/alerts."""
import ast
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from backend.test_ppe_association import logic, detection
from backend.test_ppe_defaults import BACKEND, load_source


class MaskVisibilityTests(unittest.TestCase):
    def worker(self, box=(100, 100, 300, 500), mask=False, visible=True, equipment=True):
        detections = [detection(2, list(box))]
        if equipment:
            detections += [detection(1, [150, 105, 250, 155]), detection(3, [120, 200, 280, 350])]
        if mask:
            detections.append(detection(0, [160, 160, 240, 200]))
        assessor = Mock(return_value=visible)
        return logic.compute_violations(detections, face_assessor=assessor)[0], assessor

    def test_close_up_mask_and_other_ppe_is_compliant(self):
        row, assessor = self.worker(mask=True)
        self.assertEqual(row['status'], 'COMPLIANT')
        self.assertEqual(row['mask_assessment'], 'detected')
        assessor.assert_not_called()

    def test_close_up_visible_face_without_mask_is_violation(self):
        row, _ = self.worker()
        self.assertEqual(row['missing_ppe'], ['Face Mask'])
        self.assertEqual(row['status'], 'VIOLATION')

    def test_distant_worker_cannot_trigger_mask_violation_even_if_assessor_says_yes(self):
        row, assessor = self.worker(box=(100, 100, 140, 190), equipment=False)
        self.assertNotIn('Face Mask', row['missing_ppe'])

        self.assertEqual(row['mask_assessment'], 'not assessable')
        assessor.assert_not_called()

    def test_facing_away_without_mask_is_not_assessable_not_compliant(self):
        row, _ = self.worker(visible=False)
        self.assertEqual(row['status'], 'NOT_ASSESSABLE')
        self.assertEqual(row['missing_ppe'], [])
        self.assertIsNone(row['compliance_score'])

    def test_helmet_and_vest_missing_still_raise_violations_with_unknown_mask(self):
        row, _ = self.worker(visible=False, equipment=False)
        self.assertEqual(row['missing_ppe'], ['Helmet', 'Safety Vest'])
        self.assertEqual(row['status'], 'VIOLATION')

    def test_no_frame_is_unknown_never_assumed_frontal(self):
        row = logic.compute_violations([detection(2, [0, 0, 300, 500])])[0]
        self.assertEqual(row['not_assessable'], ['Face Mask'])
        self.assertNotIn('Face Mask', row['missing_ppe'])


    def test_image_video_and_live_rules_receive_actual_frame_pixels(self):
        calls = []
        for path in ('api/upload.py', 'websocket/manager.py'):
            tree = ast.parse((BACKEND / path).read_text(encoding='utf-8'))
            calls.extend(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'compute_violations')
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(any(k.arg == 'frame' and isinstance(k.value, ast.Name) and k.value.id == 'frame' for k in call.keywords) for call in calls))


class FrontalFaceGateTests(unittest.TestCase):
    def setUp(self):
        self.module = load_source('isolated_face_visibility', BACKEND / 'detection/face_visibility.py')
        self.cascade = Mock()
        self.cascade.empty.return_value = False
        self.cv = SimpleNamespace(
            CascadeClassifier=Mock(return_value=self.cascade),
            data=SimpleNamespace(haarcascades='local/'), COLOR_BGR2GRAY=1,
            cvtColor=Mock(side_effect=lambda frame, color: frame[:, :, 0]),
        )
        import numpy as np
        self.frame = np.zeros((500, 400, 3), dtype=np.uint8)

    def visible(self, faces, box=(100, 100, 300, 500)):
        self.cascade.detectMultiScale.return_value = faces
        with patch.dict(sys.modules, {'cv2': self.cv}):
            return self.module.frontal_face_visible(self.frame, box)

    def test_centered_frontal_face_in_upper_half_can_be_assessed(self):
        self.assertTrue(self.visible([[70, 10, 50, 50]]))
        self.assertEqual(self.cv.cvtColor.call_args.args[0].shape, (200, 200, 3))
        self.cv.CascadeClassifier.assert_called_once_with('local/haarcascade_frontalface_default.xml')

    def test_no_frontal_face_is_unknown(self):
        self.assertFalse(self.visible([]))

    def test_neighboring_face_at_edge_is_not_this_workers_evidence(self):
        self.assertFalse(self.visible([[175, 10, 24, 24]]))

    def test_offscreen_or_missing_frame_is_unknown(self):
        self.assertFalse(self.module.frontal_face_visible(None, [0, 0, 200, 300]))
        self.assertFalse(self.visible([], box=(-100, -100, -50, -50)))

    def test_missing_cascade_is_unknown_instead_of_assuming_visible(self):
        self.cascade.empty.return_value = True
        self.assertFalse(self.visible([[70, 10, 50, 50]]))


if __name__ == '__main__':
    unittest.main()
