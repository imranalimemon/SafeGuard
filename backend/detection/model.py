import cv2
import numpy as np
import onnxruntime as ort
from typing import List, Dict, Tuple
from pathlib import Path

from config import settings

class PPEDetector:
    def __init__(self, model_path: str = None):
        if model_path is None:
            # Resolve relative to backend dir
            backend_dir = Path(__file__).resolve().parent.parent
            model_path = str((backend_dir / settings.MODEL_PATH).resolve())
            
        self.model_path = model_path
        self.session = ort.InferenceSession(self.model_path, providers=['CPUExecutionProvider'])
        
        model_inputs = self.session.get_inputs()
        self.input_name = model_inputs[0].name
        self.input_shape = model_inputs[0].shape  # Usually [1, 3, 640, 640]
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

    def _letterbox_geometry(self, original_shape: Tuple[int, int]):
        """Fixed-size, centered Ultralytics letterbox (auto=False, scaleup=True).

        Recompute this per image rather than storing mutable transform state:
        the detector may be shared by multiple camera threads.
        """
        orig_h, orig_w = original_shape
        gain = min(self.input_width / orig_w, self.input_height / orig_h)
        resized_shape = (round(orig_w * gain), round(orig_h * gain))
        # Odd padding puts the extra pixel on the right/bottom.
        pad_x = (self.input_width - resized_shape[0]) // 2
        pad_y = (self.input_height - resized_shape[1]) // 2
        return gain, resized_shape, (pad_x, pad_y)

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        original_shape = image.shape[:2]  # (height, width)

        _, resized_shape, (pad_x, pad_y) = self._letterbox_geometry(original_shape)
        img = cv2.resize(image, resized_shape, interpolation=cv2.INTER_LINEAR)
        img = cv2.copyMakeBorder(
            img,
            pad_y, self.input_height - resized_shape[1] - pad_y,
            pad_x, self.input_width - resized_shape[0] - pad_x,
            cv2.BORDER_CONSTANT, value=(114, 114, 114),
        )
        # BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Normalize 0-1
        img = img.astype(np.float32) / 255.0
        # HWC to CHW
        img = img.transpose((2, 0, 1))
        # Add batch dim
        input_tensor = np.ascontiguousarray(np.expand_dims(img, axis=0))
        
        return input_tensor, original_shape

    def postprocess(self, outputs, original_shape: Tuple[int, int]) -> List[Dict]:
        # YOLOv8 output is (1, 8, 8400) for 4 classes
        # Transpose to (8400, 8)
        preds = outputs[0][0].T
        
        boxes = []
        scores = []
        class_ids = []
        
        orig_h, orig_w = original_shape
        gain, _, (pad_x, pad_y) = self._letterbox_geometry(original_shape)
        
        for row in preds:
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            
            if confidence > settings.CONFIDENCE_THRESHOLD:
                cx, cy, w, h = (float(x) for x in row[:4])
                if w <= 0 or h <= 0:
                    continue

                # Keep floating-point model coordinates through NMS. OpenCV
                # expects [x, y, w, h], with x/y at the top-left.
                boxes.append([cx - w / 2, cy - h / 2, w, h])
                scores.append(confidence)
                class_ids.append(class_id)
        
        if not boxes:
            return []
            
        # Suppress duplicates only within a class: PPE may overlap a person.
        kept_indices = []
        for class_id in sorted(set(class_ids)):
            class_indices = [i for i, value in enumerate(class_ids) if value == class_id]
            indices = cv2.dnn.NMSBoxes(
                [boxes[i] for i in class_indices],
                [scores[i] for i in class_indices],
                settings.CONFIDENCE_THRESHOLD,
                settings.IOU_THRESHOLD,
            )
            kept_indices.extend(class_indices[int(i)] for i in np.asarray(indices).reshape(-1))
        kept_indices.sort(key=lambda i: scores[i], reverse=True)
        
        detections = []
        for i in kept_indices:
            bx, by, bw, bh = boxes[i]
            # Undo letterbox padding and its uniform resize, then clip every
            # edge to the original image. Ignore boxes wholly inside padding.
            x1 = max(0, min(orig_w, round((bx - pad_x) / gain)))
            y1 = max(0, min(orig_h, round((by - pad_y) / gain)))
            x2 = max(0, min(orig_w, round((bx + bw - pad_x) / gain)))
            y2 = max(0, min(orig_h, round((by + bh - pad_y) / gain)))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append({
                "bbox": [x1, y1, x2, y2],
                "class_id": class_ids[i],
                "class_name": settings.CLASS_NAMES.get(class_ids[i], "Unknown"),
                "confidence": scores[i]
            })
                
        return detections

    def detect(self, image: np.ndarray) -> List[Dict]:
        input_tensor, original_shape = self.preprocess(image)
        outputs = self.session.run(None, {self.input_name: input_tensor})
        detections = self.postprocess(outputs, original_shape)
        return detections
