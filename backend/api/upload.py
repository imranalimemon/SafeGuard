"""Validated uploads. Sync handlers run in FastAPI's worker pool, not the event loop."""
import asyncio
import json
import math
import logging
from pathlib import Path
import tempfile
import threading
import uuid
from datetime import datetime

import cv2
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Violation
from detection.model import get_detector
from detection.violation_logic import compute_violations
from detection.annotator import annotate_frame
from detection.deduplicator import deduplicator
from config import settings
from alerts.alert_manager import trigger_alerts

router = APIRouter()
_upload_slot = threading.BoundedSemaphore(1)
IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
VIDEO_TYPES = {'.mp4': 'video/mp4', '.avi': 'video/x-msvideo', '.mov': 'video/quicktime'}


def _serialize_detections(detections):
    return [{"class_id": d["class_id"], "class_name": d["class_name"],
             "confidence": round(float(d["confidence"]), 4), "bbox": [int(x) for x in d["bbox"]]}
            for d in detections]


@router.get('/api/uploads/limits')
def upload_limits():
    return {'image': {'max_bytes': settings.MAX_IMAGE_UPLOAD_BYTES, 'extensions': list(IMAGE_TYPES)},
            'video': {'max_bytes': settings.MAX_VIDEO_UPLOAD_BYTES, 'extensions': list(VIDEO_TYPES)}}


def _copy_upload(file, kind, folder):
    suffix = Path(file.filename or '').suffix.lower()
    types = IMAGE_TYPES if kind == 'image' else VIDEO_TYPES
    if suffix not in types:
        raise HTTPException(415, f'Allowed {kind} types: {", ".join(types)}')
    mime = (file.content_type or '').lower().split(';')[0]
    allowed_mime = {types[suffix], '', 'application/octet-stream'}
    if suffix == '.avi':
        allowed_mime.add('video/avi')
    if mime not in allowed_mime:
        raise HTTPException(415, 'File type does not match its extension')
    limit = settings.MAX_IMAGE_UPLOAD_BYTES if kind == 'image' else settings.MAX_VIDEO_UPLOAD_BYTES
    path = Path(folder) / ('input' + suffix)  # Never use the supplied filename as a path.
    total = 0
    with path.open('wb') as output:
        file.file.seek(0)
        while chunk := file.file.read(64 * 1024):
            total += len(chunk)
            if total > limit:
                raise HTTPException(413, f'{kind.title()} exceeds the {limit / (1024 * 1024):g} MiB upload limit')
            output.write(chunk)
    if not total:
        raise HTTPException(400, 'The uploaded file is empty')
    return path


def _read_image(path):
    try:
        with Image.open(path) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise HTTPException(415, 'Image content must be JPEG, PNG or WEBP')
            if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                raise HTTPException(413, 'Image dimensions exceed the pixel limit')
            image.verify()
    except Image.DecompressionBombError:
        raise HTTPException(413, 'Image dimensions exceed the pixel limit')
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(415, 'The image is corrupt or cannot be decoded')
    frame = cv2.imread(str(path))
    if frame is None:
        raise HTTPException(415, 'The image cannot be decoded')
    return frame


def _workers(detections, frame):
    workers = compute_violations(detections, frame=frame)
    for index, worker in enumerate(workers, 1):
        worker['worker_id'] = index
        worker['ppe_status'] = {
            ppe: ('present' if ppe in worker['has_ppe'] else
                  'mask not assessable' if ppe == 'Face Mask' and worker['mask_assessment'] == 'not assessable' else
                  'missing' if ppe in worker['missing_ppe'] else 'not required')
            for ppe in ('Helmet', 'Safety Vest', 'Face Mask')
        }
    return workers


def _save_frame(frame, detections, workers, outputs):
    path = Path(settings.SCREENSHOT_DIR) / f'{uuid.uuid4()}.jpg'
    outputs.append(path)
    if not cv2.imwrite(str(path), annotate_frame(frame.copy(), detections, workers)):
        raise RuntimeError('Could not save the annotated result')
    return f'/screenshots/{path.name}', str(path)


def _notify(payload, screenshot):
    # Sync background task: blocking transports also stay off the event loop.
    asyncio.run(trigger_alerts(payload, screenshot))


def _record(db, tasks, source, filename, frame_number, frame, detections, workers, outputs, retained, image=None):
    pending = [w for w in workers if w['status'] == 'VIOLATION']
    accepted, suppressed = [], 0
    for v in pending:
        if deduplicator.should_log(source, v['missing_ppe'], person_bbox=v['person_bbox']):
            accepted.append(v)
        else:
            suppressed += 1
    if not accepted:
        return [], suppressed
    image = image or _save_frame(frame, detections, workers, outputs)
    url, disk = image
    rows = []
    for worker in accepted:
        row = Violation(timestamp=datetime.utcnow(),
            violation_type=f"Missing: {', '.join(worker['missing_ppe'])}",
            person_count=len(workers), violation_count=len(pending), screenshot_path=url,
            confidence=worker['confidence'], missing_ppe=', '.join(worker['missing_ppe']),
            details=f'{filename}' + (f' - frame {frame_number}' if frame_number else ''),
            bbox=json.dumps(worker['person_bbox']), detections=json.dumps(_serialize_detections(detections)),
            source=source, mask_assessment=worker['mask_assessment'])
        db.add(row); rows.append(row)
    db.commit()  # Short transaction per analyzed frame; never hold a video-long DB lock.
    retained.add(Path(disk))
    created = []
    for row in rows:
        db.refresh(row)
        payload = {key: getattr(row, key) for key in ('id', 'violation_type', 'missing_ppe', 'person_count', 'confidence', 'details', 'source')}
        payload.update(timestamp=str(row.timestamp), screenshot_path=url, frame_number=frame_number)
        created.append(payload)
        tasks.add_task(_notify, payload, disk)
    return created, suppressed


def _process_image(path, filename, db, tasks, outputs, retained):
    frame = _read_image(path)
    detections = get_detector().detect(frame)
    workers = _workers(detections, frame)
    image = _save_frame(frame, detections, workers, outputs)
    created, suppressed = _record(db, tasks, 'image_upload', filename, None, frame,
        detections, workers, outputs, retained, image)
    return {'media_type': 'image', 'annotated_image_url': image[0],
        'detections': _serialize_detections(detections), 'workers': workers,
        'violations': [w for w in workers if w['status'] == 'VIOLATION'], 'created_violations': created,
        'stats': {'total_persons': len(workers), 'compliant': sum(w['status'] == 'COMPLIANT' for w in workers),
            'mask_not_assessable': sum(w['mask_assessment'] == 'not assessable' for w in workers),
            'violations': sum(w['status'] == 'VIOLATION' for w in workers),
            'violations_created': len(created), 'suppressed_by_cooldown': suppressed}}


def _process_video(path, filename, db, tasks, outputs, retained):
    with path.open('rb') as header:
        signature = header.read(12)
    if path.suffix.lower() == '.avi':
        valid = signature[:4] == b'RIFF' and signature[8:12] == b'AVI '
    else:
        valid = len(signature) >= 8 and signature[4:8] in {b'ftyp', b'moov', b'mdat', b'wide', b'free', b'skip'}
    if not valid:
        raise HTTPException(415, 'Video content does not match an MP4, AVI or MOV container')
    cap = cv2.VideoCapture(str(path))
    decoded = analyzed = observations = max_workers = violating = suppressed = unknown = 0
    key_frames, violation_frames, created = [], [], []
    try:
        if not cap.isOpened():
            raise HTTPException(415, 'The video cannot be opened; check its format/codec')
        hint = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        key_stride = max(3, int(hint) // 5) if math.isfinite(hint) and hint > 0 else 90
        last_key = -key_stride
        detector = get_detector()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            decoded += 1
            if decoded != 1 and decoded % 3:
                continue
            analyzed += 1
            detections = detector.detect(frame)
            workers = _workers(detections, frame)
            observations += len(workers); max_workers = max(max_workers, len(workers))
            unknown += sum(w['mask_assessment'] == 'not assessable' for w in workers)
            bad = [w for w in workers if w['status'] == 'VIOLATION']
            violating += len(bad)
            image = None
            if len(key_frames) < 6 and decoded - last_key >= key_stride:
                image = _save_frame(frame, detections, workers, outputs)
                key_frames.append({'frame_number': decoded, 'screenshot_url': image[0], 'workers': workers})
                last_key = decoded
            rows, skipped = _record(db, tasks, 'video_upload', filename, decoded, frame,
                detections, workers, outputs, retained, image)
            created.extend(rows); suppressed += skipped
            if bad:
                violation_frames.append({'frame_number': decoded, 'violations': bad,
                    'created_ids': [r['id'] for r in rows]})
        if not decoded:
            raise HTTPException(415, 'The video has no decodable frames')
    finally:
        cap.release()
    return {'media_type': 'video', 'total_frames': decoded, 'frames_processed': analyzed,
        'worker_observations': observations, 'max_workers_in_frame': max_workers,
        'violations_detected': violating, 'violations_logged': len(created), 'suppressed_by_cooldown': suppressed,
        'mask_not_assessable_observations': unknown, 'key_frames': key_frames,
        'violation_frames': violation_frames, 'created_violations': created}


def _upload(kind, tasks, file, db):
    acquired = False
    outputs, retained = [], set()
    try:
        acquired = _upload_slot.acquire(blocking=False)
        if not acquired:
            raise HTTPException(429, 'Another upload is processing. Try again when it finishes.')
        with tempfile.TemporaryDirectory(prefix='safeguard-upload-') as folder:
            path = _copy_upload(file, kind, folder)
            process = _process_image if kind == 'image' else _process_video
            result = process(path, Path(file.filename or '').name, db, tasks, outputs, retained)
            result['filename'] = Path(file.filename or '').name
            retained.update(outputs)
            return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        logging.getLogger(__name__).exception('Upload processing failed')
        db.rollback()
        raise HTTPException(500, 'Upload processing failed. Check the backend log and retry.') from exc
    finally:
        # Only newly generated, uncommitted outputs can be removed on failure.
        for output in outputs:
            if output not in retained:
                output.unlink(missing_ok=True)
        file.file.close()
        if acquired:
            _upload_slot.release()


@router.post('/api/upload/image')
def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return _upload('image', background_tasks, file, db)


@router.post('/api/upload/video')
def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return _upload('video', background_tasks, file, db)
