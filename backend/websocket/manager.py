"""
SafeGuard AI — WebSocket Live Stream Manager
"""
import cv2
import base64
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

from detection.model import PPEDetector
from detection.violation_logic import compute_violations
from detection.annotator import annotate_frame
from config import settings

router = APIRouter()
_detector = None


def get_detector():
    global _detector
    if _detector is None:
        _detector = PPEDetector()
    return _detector


class ConnectionManager:
    """Manages WebSocket connections for live streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time video stream with PPE detection."""
    await manager.connect(websocket)
    det = get_detector()
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            await websocket.send_json({"error": "Cannot open webcam"})
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue

            # Run detection pipeline
            detections = det.detect(frame)
            violations = compute_violations(detections)
            annotated = annotate_frame(frame.copy(), detections, violations)

            # Encode frame as base64 JPEG
            _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_base64 = base64.b64encode(buffer).decode("utf-8")

            # Calculate stats
            total_persons = sum(1 for d in detections if d["class_id"] == settings.PERSON_CLASS_ID)
            violating = sum(1 for v in violations if v["status"] == "VIOLATION")
            compliant = total_persons - violating
            compliance_rate = (compliant / total_persons * 100) if total_persons > 0 else 100.0

            data = {
                "frame": frame_base64,
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
                        "status": v["status"],
                    }
                    for v in violations
                    if v["status"] == "VIOLATION"
                ],
                "stats": {
                    "persons": total_persons,
                    "compliant": compliant,
                    "violations": violating,
                    "compliance_rate": round(compliance_rate, 1),
                },
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.033)  # ~30 FPS cap

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
    finally:
        if cap is not None:
            cap.release()
