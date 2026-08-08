from typing import List, Dict
from config import settings

def compute_iou(box_a: List[int], box_b: List[int]) -> float:
    # box format: [x1, y1, x2, y2]
    xA = max(box_a[0], box_b[0])
    yA = max(box_a[1], box_b[1])
    xB = min(box_a[2], box_b[2])
    yB = min(box_a[3], box_b[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    boxBArea = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def compute_violations(detections: List[Dict], required_ppe: List[str] = None) -> List[Dict]:
    if required_ppe is None:
        required_ppe = ["Helmet", "Safety Vest"]
        
    persons = [d for d in detections if d["class_id"] == settings.PERSON_CLASS_ID]
    ppes = [d for d in detections if d["class_id"] != settings.PERSON_CLASS_ID]
    
    results = []
    
    for person in persons:
        has_ppe = []
        for ppe in ppes:
            if ppe["class_name"] not in required_ppe:
                continue
                
            iou = compute_iou(person["bbox"], ppe["bbox"])
            if iou > settings.VIOLATION_IOU_THRESHOLD:
                if ppe["class_name"] not in has_ppe:
                    has_ppe.append(ppe["class_name"])
                    
        missing_ppe = [item for item in required_ppe if item not in has_ppe]
        
        status = "VIOLATION" if missing_ppe else "COMPLIANT"
        
        results.append({
            "person_bbox": person["bbox"],
            "missing_ppe": missing_ppe,
            "has_ppe": has_ppe,
            "status": status,
            "confidence": person["confidence"]
        })
        
    return results
