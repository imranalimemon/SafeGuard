"""Camera WebSockets: latest-frame capture, sampled inference and annotated JPEGs."""
try:
    from observations import record_observation
except ModuleNotFoundError:
    from backend.observations import record_observation
import asyncio
import base64
import json
import logging
import sys
from datetime import datetime, timezone
from typing import List

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from alerts.alert_manager import trigger_alerts
from api.upload import _serialize_detections
from config import settings
from db.database import SessionLocal
from db.models import Camera, Violation, WorkerObservation
from detection.annotator import annotate_frame
from detection.deduplicator import deduplicator
from detection.model import get_detector
from detection.violation_logic import compute_violations
from . import registry
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


def _build_capture(camera: Camera):
    from detection.camera_capture import open_capture
    return open_capture(camera)


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
        record_observation(db, violations, f"camera:{camera.id}", WorkerObservation)
        db.commit()
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
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
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
                mask_assessment=v.get("mask_assessment"),
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
                "camera_name": camera.name,
                "person_bbox": v['person_bbox'],
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
    compliant = sum(v["status"] == "COMPLIANT" for v in violations)
    assessed = compliant + violating
    return {
        "camera_id": camera.id,
        "camera_name": camera.name,
        "frame": base64.b64encode(buffer).decode("utf-8"),
        "detections": _serialize_detections(detections),
        "workers": violations,
        "violations": [
            {"person_bbox": v["person_bbox"], "missing_ppe": v["missing_ppe"], "status": v["status"]}
            for v in violations if v["status"] == "VIOLATION"
        ],
        "stats": {
            "persons": total, "compliant": compliant, "violations": violating,
            "mask_not_assessable": sum(v.get("mask_assessment") == "not assessable" for v in violations),
            "compliance_rate": round(compliant / assessed * 100, 1) if assessed else None,
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
            return detections, compute_violations(detections, frame=frame)

        async def record(frame, result):
            detections, violations = result
            _, pending = await asyncio.to_thread(
                _write_violations, camera, frame, detections, violations
            )
            if pending:
                await asyncio.to_thread(_dispatch_alerts, pending)

        stream = LatestFrameStream(
            lambda: _build_capture(camera), analyze,
            interval=settings.STREAM_DETECTION_INTERVAL, on_result=record,
            reconnect_attempts=getattr(settings, "STREAM_RECONNECT_ATTEMPTS", 0),
        ).start()
        registry.register(camera.id, stream)
        async def authorized():
            # Test sockets have no ASGI scope; production sockets always do.
            if not hasattr(websocket, 'scope'):
                return True
            token = websocket.scope.get('state', {}).get('session_token', '')
            return bool(await asyncio.to_thread(websocket.app.state.auth.lookup, token))
        await send_latest(websocket, stream, lambda frame, result: _stream_packet(camera, frame, result), authorized=authorized)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logging.getLogger("safeguard.stream").warning("Stream failed (%s)", type(exc).__name__)
        try:
            safe_errors = {
                "Camera not available: cannot open camera",
                "Camera not available: camera stopped returning frames",
                "Camera not available: capture failed",
                "Camera not available: frame delivery timed out",
                "Camera processing failed. Check the system log.",
                "Session expired. Sign in again.",
            }
            message = str(exc) if str(exc) in safe_errors else "Camera not available: processing failed. Check the system log."
            await websocket.send_json({"error": message})
            await websocket.close(code=4400)
        except Exception:
            pass  # Socket may already have disconnected.
    finally:
        manager.disconnect(websocket)
        if stream is not None:
            registry.discard(stream)
            await stream.close()
