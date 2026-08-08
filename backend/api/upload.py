"""
SafeGuard AI — Image & Video Upload API
"""
import os
import shutil
import uuid
import cv2
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from db.database import get_db
from db.models import Violation
from detection.model import PPEDetector
from detection.violation_logic import compute_violations
from detection.annotator import annotate_frame
from config import settings
from alerts.alert_manager import trigger_alerts

router = APIRouter()
_detector = None


def get_detector():
    """Lazy-load the PPE detector singleton."""
    global _detector
    if _detector is None:
        _detector = PPEDetector()
    return _detector


@router.post("/api/upload/image")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    det = get_detector()

    # Save uploaded file to temp
    os.makedirs("temp", exist_ok=True)
    temp_path = f"temp/{uuid.uuid4()}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Read and process image
    image = cv2.imread(temp_path)
    if image is None:
        os.remove(temp_path)
        return {"error": "Could not read image file"}

    detections = det.detect(image)
    violations = compute_violations(detections)
    annotated = annotate_frame(image.copy(), detections, violations)

    # Save annotated screenshot
    screenshot_filename = f"{uuid.uuid4()}.jpg"
    screenshot_path = os.path.join(settings.SCREENSHOT_DIR, screenshot_filename)
    cv2.imwrite(screenshot_path, annotated)
    screenshot_url = f"/screenshots/{screenshot_filename}"

    # Compute stats
    total_persons = sum(1 for d in detections if d["class_id"] == settings.PERSON_CLASS_ID)
    violating = sum(1 for v in violations if v["status"] == "VIOLATION")
    compliant = total_persons - violating

    # Log violations to database
    for v in violations:
        if v["status"] == "VIOLATION":
            db_violation = Violation(
                timestamp=datetime.utcnow(),
                violation_type=f"Missing: {', '.join(v['missing_ppe'])}",
                person_count=total_persons,
                violation_count=violating,
                screenshot_path=screenshot_url,
                confidence=v["confidence"],
                missing_ppe=", ".join(v["missing_ppe"]),
                details=f"Image upload: {file.filename}",
            )
            db.add(db_violation)
            db.commit()
            db.refresh(db_violation)
            
            violation_dict = {
                "id": db_violation.id,
                "violation_type": db_violation.violation_type,
                "missing_ppe": db_violation.missing_ppe,
                "person_count": db_violation.person_count,
                "confidence": db_violation.confidence,
                "screenshot_path": screenshot_path,
                "timestamp": str(db_violation.timestamp)
            }
            background_tasks.add_task(trigger_alerts, violation_dict, screenshot_path)

    # Cleanup temp
    os.remove(temp_path)

    return {
        "detections": [
            {
                "class_id": d["class_id"],
                "class_name": d["class_name"],
                "confidence": round(d["confidence"], 3),
                "bbox": d["bbox"],
            }
            for d in detections
        ],
        "violations": [
            {
                "person_bbox": v["person_bbox"],
                "missing_ppe": v["missing_ppe"],
                "has_ppe": v["has_ppe"],
                "status": v["status"],
                "confidence": round(v["confidence"], 3),
            }
            for v in violations
        ],
        "annotated_image_url": screenshot_url,
        "stats": {
            "total_persons": total_persons,
            "compliant": compliant,
            "violations": violating,
        },
    }


@router.post("/api/upload/video")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    det = get_detector()
    os.makedirs("temp", exist_ok=True)
    temp_path = f"temp/{uuid.uuid4()}_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cap = cv2.VideoCapture(temp_path)
    frame_count = 0
    violation_frames = []
    total_violations_detected = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if frame_count % 3 != 0:
            continue

        detections = det.detect(frame)
        violations = compute_violations(detections)
        violating = [v for v in violations if v["status"] == "VIOLATION"]

        if violating:
            annotated = annotate_frame(frame.copy(), detections, violations)
            screenshot_filename = f"{uuid.uuid4()}.jpg"
            screenshot_path = os.path.join(settings.SCREENSHOT_DIR, screenshot_filename)
            cv2.imwrite(screenshot_path, annotated)
            screenshot_url = f"/screenshots/{screenshot_filename}"

            violation_frames.append(
                {
                    "frame_number": frame_count,
                    "violations": [
                        {"missing_ppe": v["missing_ppe"], "status": v["status"]}
                        for v in violating
                    ],
                    "screenshot_url": screenshot_url,
                }
            )
            total_violations_detected += len(violating)

            # Log to DB
            total_persons = sum(1 for d in detections if d["class_id"] == settings.PERSON_CLASS_ID)
            for v in violating:
                db_violation = Violation(
                    timestamp=datetime.utcnow(),
                    violation_type=f"Missing: {', '.join(v['missing_ppe'])}",
                    person_count=total_persons,
                    violation_count=len(violating),
                    screenshot_path=screenshot_url,
                    confidence=v["confidence"],
                    missing_ppe=", ".join(v["missing_ppe"]),
                    details=f"Video frame #{frame_count}",
                )
                db.add(db_violation)
                db.commit()
                db.refresh(db_violation)
                
                violation_dict = {
                    "id": db_violation.id,
                    "violation_type": db_violation.violation_type,
                    "missing_ppe": db_violation.missing_ppe,
                    "person_count": db_violation.person_count,
                    "confidence": db_violation.confidence,
                    "screenshot_path": screenshot_path,
                    "timestamp": str(db_violation.timestamp)
                }
                background_tasks.add_task(trigger_alerts, violation_dict, screenshot_path)

    cap.release()
    os.remove(temp_path)

    return {
        "total_frames": frame_count,
        "violations_detected": total_violations_detected,
        "violation_frames": violation_frames,
    }
