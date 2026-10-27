"""Camera WebSockets: latest-frame capture, sampled inference and annotated JPEGs."""
import asyncio
import base64
import json
import sys
from datetime import datetime
from typing import List

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from alerts.alert_manager import trigger_alerts
from api.upload import _serialize_detections
from config import settings
from db.database import SessionLocal
from db.models import Camera, Violation
from detection.annotator import annotate_frame
from detection.deduplicator import deduplicator
from detection.model import get_detector
from detection.violation_logic import compute_violations
from .live import LatestFrameStream, send_latest

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for live streaming.

    Phase 2 keeps a flat list — one camera per dashboard session for the
    minimum viable slice. Multi-camera grid is deferred.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


def _build_capture(camera: Camera) -> cv2.VideoCapture:
    """Resolve a Camera row to an open cv2.VideoCapture. Caller is responsible
    for releasing it."""
    if camera.source_type == "webcam":
        # url stores the integer index as a string; default to 0.
        idx = int(camera.url) if (camera.url and camera.url.isdigit()) else 0
        # Prefer DirectShow on Windows — MSMF (the default) often returns
        # `isOpened() == True` even when no real device is present, which
        # makes the live stream silently show a black/empty frame.
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        return cv2.VideoCapture(idx, backend)
    # ip / rtsp — inject credentials if the row carries them and the URL
    # doesn't already include them.
    url = camera.url or ""
    if camera.username and camera.password and "://" in url and "@" not in url.split("://", 1)[1]:
        scheme, rest = url.split("://", 1)
        url = f"{scheme}://{camera.username}:{camera.password}@{rest}"
    return cv2.VideoCapture(url)


def _write_violations(camera: Camera, frame, detections, violations) -> tuple[int, list[dict]]:
    """Persist violations to the DB and capture evidence screenshots.
    Runs in a thread via run_in_executor.
    Returns (rows_written, list_of_violation_dicts_to_alert)."""
    import uuid
    import os

    full_detections_json = json.dumps(_serialize_detections(detections))
    written = 0
    pending_alerts: list[dict] = []
    db = SessionLocal()

    # Capture an annotated screenshot ONCE per frame (shared across all
    # violations in this frame). Only created if at least one violation
    # passes the dedup filter.
    screenshot_url = None
    screenshot_disk_path = None

    try:
        for v in violations:
            if v["status"] != "VIOLATION":
                continue
            source = f"camera:{camera.id}"
            if not deduplicator.should_log(source, v["missing_ppe"], person_bbox=v["person_bbox"]):
                continue

            # Save the annotated screenshot on the first real violation in this frame
            if screenshot_url is None:
                annotated_evidence = annotate_frame(frame.copy(), detections, violations)
                screenshot_filename = f"{uuid.uuid4()}.jpg"
                screenshot_disk_path = os.path.join(settings.SCREENSHOT_DIR, screenshot_filename)
                cv2.imencode(".jpg", annotated_evidence, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(screenshot_disk_path)
                screenshot_url = f"/screenshots/{screenshot_filename}"

            row = Violation(
                timestamp=datetime.utcnow(),
                violation_type=f"Missing: {', '.join(v['missing_ppe'])}",
                person_count=len(violations),
                violation_count=sum(1 for vv in violations if vv["status"] == "VIOLATION"),
                screenshot_path=screenshot_url,
                confidence=v["confidence"],
                missing_ppe=", ".join(v["missing_ppe"]),
                details=f"Live camera: {camera.name} ({camera.location or 'unknown location'})",
                bbox=json.dumps([int(x) for x in v["person_bbox"]]),
                detections=full_detections_json,
                source=source,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            written += 1
            pending_alerts.append({
                "id": row.id,
                "violation_type": row.violation_type,
                "missing_ppe": row.missing_ppe,
                "person_count": row.person_count,
                "confidence": row.confidence,
                "screenshot_path": screenshot_url,
                "screenshot_disk_path": screenshot_disk_path,
                "timestamp": str(row.timestamp),
                "details": row.details,
                "source": row.source,
            })
    finally:
        db.close()
    return written, pending_alerts


def _stream_packet(camera, frame, result):
    detections, violations = result if result is not None else ([], [])
    annotated = annotate_frame(frame.copy(), detections, violations)
    ok, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("Cannot encode camera frame")
    total = len(violations)
    violating = sum(v["status"] == "VIOLATION" for v in violations)
    return {
        "camera_id": camera.id,
        "camera_name": camera.name,
        "frame": base64.b64encode(buffer).decode("utf-8"),
        "detections": _serialize_detections(detections),
        "violations": [
            {"person_bbox": v["person_bbox"], "missing_ppe": v["missing_ppe"], "status": v["status"]}
            for v in violations if v["status"] == "VIOLATION"
        ],
        "stats": {
            "persons": total, "compliant": total - violating, "violations": violating,
            "compliance_rate": round((total - violating) / total * 100, 1) if total else None,
        } if result is not None else None,
    }


def _dispatch_alerts(pending_alerts):
    # Existing alert transports can block; keep them off the stream event loop.
    async def dispatch():
        for vdata in pending_alerts:
            try:
                path = vdata.get("screenshot_disk_path") or vdata.get("screenshot_path")
                await trigger_alerts(vdata, screenshot_path=path)
            except Exception as exc:
                print(f"[WS] alert trigger failed: {exc}")
    asyncio.run(dispatch())


@router.websocket("/ws/stream/{camera_id}")
async def websocket_endpoint(websocket: WebSocket, camera_id: int):
    """Stream latest frames, reusing sampled inference between detections."""
    await manager.connect(websocket)
    stream = None
    try:
        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
        finally:
            db.close()
        if camera is None:
            await websocket.send_json({"error": f"Camera {camera_id} not found"})
            await websocket.close(code=4404)
            return
        if not camera.enabled:
            await websocket.send_json({"error": f"Camera '{camera.name}' is disabled"})
            await websocket.close(code=4403)
            return
        det = await asyncio.to_thread(get_detector)

        def analyze(frame):
            detections = det.detect(frame)
            return detections, compute_violations(detections)

        async def record(frame, result):
            detections, violations = result
            if violations:
                _, pending = await asyncio.to_thread(
                    _write_violations, camera, frame, detections, violations
                )
                if pending:
                    await asyncio.to_thread(_dispatch_alerts, pending)

        stream = LatestFrameStream(
            lambda: _build_capture(camera), analyze,
            interval=settings.STREAM_DETECTION_INTERVAL, on_result=record,
        ).start()
        await send_latest(websocket, stream, lambda frame, result: _stream_packet(camera, frame, result))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[WS] {exc}")
        try:
            message = str(exc) or "Camera not available: stream timed out"
            await websocket.send_json({"error": message})
            await websocket.close(code=4400)
        except Exception:
            pass  # Socket may already have disconnected.
    finally:
        manager.disconnect(websocket)
        if stream is not None:
            await stream.close()
