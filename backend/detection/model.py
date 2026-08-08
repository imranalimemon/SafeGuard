import os
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

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        original_shape = image.shape[:2]  # (height, width)
        
        # Resize to 640x640
        img = cv2.resize(image, (self.input_width, self.input_height))
        # BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Normalize 0-1
        img = img.astype(np.float32) / 255.0
        # HWC to CHW
        img = img.transpose((2, 0, 1))
        # Add batch dim
        input_tensor = np.expand_dims(img, axis=0)
        
        return input_tensor, original_shape

    def postprocess(self, outputs, original_shape: Tuple[int, int]) -> List[Dict]:
        # YOLOv8 output is (1, 8, 8400) for 4 classes
        # Transpose to (8400, 8)
        preds = outputs[0][0].T
        
        boxes = []
        scores = []
        class_ids = []
        
        orig_h, orig_w = original_shape
        x_factor = orig_w / self.input_width
        y_factor = orig_h / self.input_height
        
        for row in preds:
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            
            if confidence > settings.CONFIDENCE_THRESHOLD:
                cx, cy, w, h = row[:4]
                
                # Scale to original image dimensions
                sx = cx * x_factor
                sy = cy * y_factor
                sw = w * x_factor
                sh = h * y_factor
                
                # NMS expects [x, y, w, h] where x,y is top-left
                x1 = sx - sw / 2
                y1 = sy - sh / 2
                
                boxes.append([int(x1), int(y1), int(sw), int(sh)])
                scores.append(confidence)
                class_ids.append(class_id)
        
        if not boxes:
            return []
            
        # Apply NMS (boxes in [x, y, w, h] format)
        indices = cv2.dnn.NMSBoxes(boxes, scores, settings.CONFIDENCE_THRESHOLD, settings.IOU_THRESHOLD)
        
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                bx, by, bw, bh = boxes[i]
                detections.append({
                    "bbox": [max(0, bx), max(0, by), bx + bw, by + bh],
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
