"""Isolated detector tests: synthetic images/outputs, no ONNX model or app imports."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


def load_detector_class():
    # Real config imports read .env and create storage directories. Keep both
    # config and ONNX Runtime out of these preprocessing/postprocessing tests.
    config = ModuleType("config")
    config.settings = SimpleNamespace(
        CONFIDENCE_THRESHOLD=0.5,
        IOU_THRESHOLD=0.45,
        CLASS_NAMES={0: "Face Mask", 1: "Helmet", 2: "Person", 3: "Safety Vest"},
    )
    runtime = ModuleType("onnxruntime")
    runtime.InferenceSession = Mock(side_effect=AssertionError("No real model allowed"))
    spec = importlib.util.spec_from_file_location(
        "isolated_detection_model", Path(__file__).parent / "detection" / "model.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"config": config, "onnxruntime": runtime}):
        spec.loader.exec_module(module)
    return module.PPEDetector


PPEDetector = load_detector_class()


class DetectorProcessingTests(unittest.TestCase):
    def setUp(self):
        # Skip __init__: a session/model is unnecessary for image/box processing.
        self.detector = PPEDetector.__new__(PPEDetector)
        self.detector.input_height = 640
        self.detector.input_width = 640

    @staticmethod
    def outputs(*boxes):
        """Build 1x8x8400 outputs from (xyxy, class_id, confidence) tuples."""
        predictions = np.zeros((1, 8, 8400), dtype=np.float32)
        for index, (bbox, class_id, confidence) in enumerate(boxes):
            x1, y1, x2, y2 = bbox
            predictions[0, :4, index] = (
                (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
            )
            predictions[0, 4 + class_id, index] = confidence
        return [predictions]

    def test_nms_keeps_overlapping_person_and_vest(self):
        outputs = self.outputs(
            ([100, 100, 300, 400], 2, 0.95),
            ([100, 100, 300, 400], 3, 0.90),
        )
        detections = self.detector.postprocess(outputs, (640, 640))
        self.assertEqual(
            {d["class_name"] for d in detections}, {"Person", "Safety Vest"}
        )

    def test_nms_suppresses_same_class_duplicates_only(self):
        outputs = self.outputs(
            ([100, 100, 300, 400], 2, 0.95),
            ([105, 105, 305, 405], 2, 0.80),
            ([450, 100, 550, 300], 2, 0.75),
        )
        detections = self.detector.postprocess(outputs, (640, 640))
        self.assertEqual(
            [d["bbox"] for d in detections],
            [[100, 100, 300, 400], [450, 100, 550, 300]],
        )

    def test_empty_and_below_threshold_outputs(self):
        for outputs in (self.outputs(), self.outputs(([50, 50, 100, 100], 1, 0.49))):
            with self.subTest():
                self.assertEqual(self.detector.postprocess(outputs, (640, 640)), [])

    def test_four_class_output_mapping_without_objectness(self):
        outputs = self.outputs(*(
            ([20 + i * 120, 20, 100 + i * 120, 100], i, 0.9)
            for i in range(4)
        ))
        detections = self.detector.postprocess(outputs, (640, 640))
        self.assertEqual(
            {d["class_id"]: d["class_name"] for d in detections},
            {0: "Face Mask", 1: "Helmet", 2: "Person", 3: "Safety Vest"},
        )

    def test_rgb_normalization_and_tensor_layout(self):
        image = np.full((320, 320, 3), [0, 127, 255], dtype=np.uint8)
        tensor, original_shape = self.detector.preprocess(image)
        self.assertEqual(original_shape, (320, 320))
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertEqual(tensor.dtype, np.float32)
        np.testing.assert_allclose(tensor[0, :, 320, 320], [1.0, 127 / 255, 0.0])
        self.assertTrue(tensor.flags.c_contiguous)

    def test_landscape_letterbox_preserves_aspect_ratio(self):
        tensor, _ = self.detector.preprocess(np.zeros((320, 640, 3), dtype=np.uint8))
        np.testing.assert_allclose(tensor[:, :, :160, :], 114 / 255)
        np.testing.assert_allclose(tensor[:, :, 160:480, :], 0.0)
        np.testing.assert_allclose(tensor[:, :, 480:, :], 114 / 255)

    def test_portrait_letterbox_preserves_aspect_ratio(self):
        tensor, _ = self.detector.preprocess(np.zeros((640, 320, 3), dtype=np.uint8))
        np.testing.assert_allclose(tensor[:, :, :, :160], 114 / 255)
        np.testing.assert_allclose(tensor[:, :, :, 160:480], 0.0)
        np.testing.assert_allclose(tensor[:, :, :, 480:], 114 / 255)

    def test_odd_letterbox_padding(self):
        tensor, _ = self.detector.preprocess(np.zeros((333, 1000, 3), dtype=np.uint8))
        # Resize to 213x640, then split 427 padding rows into 213 + 214.
        np.testing.assert_allclose(tensor[:, :, :213, :], 114 / 255)
        np.testing.assert_allclose(tensor[:, :, 213:426, :], 0.0)
        np.testing.assert_allclose(tensor[:, :, 426:, :], 114 / 255)

    def test_boxes_map_back_after_letterboxing(self):
        cases = [
            ((720, 1280), [100, 50, 600, 700], [50, 165, 300, 490]),
            ((1280, 720), [50, 100, 700, 600], [165, 50, 490, 300]),
            ((333, 1000), [100, 10, 900, 320], [64, 219.4, 576, 417.8]),
            ((1000, 333), [10, 100, 320, 900], [219.4, 64, 417.8, 576]),
        ]
        for shape, original_box, model_box in cases:
            with self.subTest(shape=shape):
                detections = self.detector.postprocess(
                    self.outputs((model_box, 2, 0.9)), shape
                )
                self.assertEqual(detections[0]["bbox"], original_box)

    def test_boxes_clip_to_image_and_padding_only_boxes_are_dropped(self):
        outputs = self.outputs(
            ([0, 0, 640, 640], 2, 0.95),
            ([10, 10, 40, 100], 1, 0.90),
        )
        detections = self.detector.postprocess(outputs, (320, 640))
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["bbox"], [0, 0, 640, 320])

    def test_detect_uses_preprocessing_and_inverse_box_mapping(self):
        self.detector.input_name = "images"
        self.detector.session = Mock()
        self.detector.session.run.return_value = self.outputs(
            ([40, 200, 140, 300], 2, 0.9)
        )
        image = np.zeros((320, 640, 3), dtype=np.uint8)
        detections = self.detector.detect(image)
        self.assertEqual(detections[0]["bbox"], [40, 40, 140, 140])
        tensor = self.detector.session.run.call_args.args[1]["images"]
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        np.testing.assert_allclose(tensor[:, :, :160, :], 114 / 255)


if __name__ == "__main__":
    unittest.main()
