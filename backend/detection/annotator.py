import cv2
import numpy as np
from typing import List, Dict
from config import settings

def annotate_frame(frame: np.ndarray, detections: List[Dict], violations: List[Dict]) -> np.ndarray:
    annotated = frame.copy()
    has_violation = any(v["status"] == "VIOLATION" for v in violations)
    
    # Draw warning banner
    if has_violation:
        cv2.rectangle(annotated, (0, 0), (annotated.shape[1], 50), settings.VIOLATION_COLOR, -1)
        cv2.putText(annotated, "WARNING: PPE VIOLATION DETECTED", (20, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                    
    # Draw all PPE detections
    for det in detections:
        if det["class_id"] == settings.PERSON_CLASS_ID:
            continue
            
        box = det["bbox"]
        class_name = det["class_name"]
        color = settings.CLASS_COLORS.get(class_name, (255, 255, 255))
        # Convert RGB to BGR for cv2
        color_bgr = (color[2], color[1], color[0])
        
        cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color_bgr, 2)
        
        # Label
        label = f"{class_name} {det['confidence']:.2f}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (box[0], box[1] - 20), (box[0] + w, box[1]), color_bgr, -1)
        cv2.putText(annotated, label, (box[0], box[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    # Draw persons with violation status
    for v in violations:
        box = v["person_bbox"]
        
        if v["status"] == "COMPLIANT":
            color = settings.COMPLIANT_COLOR
            label = "COMPLIANT"
        else:
            color = settings.VIOLATION_COLOR
            missing_str = ", ".join(v["missing_ppe"])
            label = f"Missing: {missing_str}"
            
        cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color, 2)
        
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (box[0], box[1] - 25), (box[0] + w, box[1]), color, -1)
        cv2.putText(annotated, label, (box[0], box[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
    return annotated
