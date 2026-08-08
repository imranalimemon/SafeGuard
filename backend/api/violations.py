import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from db.database import get_db
from db.models import Violation

router = APIRouter()


def _safe_json_load(value, default):
    """Parse JSON text fields back into native Python objects. Returns
    `default` when the value is None, empty, or malformed — so a corrupted
    row never crashes the dashboard."""
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _serialize_violation(row: Violation) -> dict:
    """Convert a SQLAlchemy Violation row into a JSON-safe dict.

    The `bbox` and `detections` columns are stored as JSON text (SQLite has
    no JSON type); we parse them here so the API consumer receives native
    arrays/objects rather than escaped strings.
    """
    return {
        "id": row.id,
        "timestamp": row.timestamp,
        "violation_type": row.violation_type,
        "person_count": row.person_count,
        "violation_count": row.violation_count,
        "screenshot_path": row.screenshot_path,
        "confidence": row.confidence,
        "alert_sent": row.alert_sent,
        "missing_ppe": row.missing_ppe,
        "details": row.details,
        "source": row.source,
        "bbox": _safe_json_load(row.bbox, None),
        "detections": _safe_json_load(row.detections, []),
    }


@router.get("/api/violations")
def get_violations(
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Violation)
    if start_date:
        query = query.filter(Violation.timestamp >= start_date)
    if end_date:
        query = query.filter(Violation.timestamp <= end_date)
    rows = query.order_by(Violation.timestamp.desc()).offset(offset).limit(limit).all()
    return [_serialize_violation(r) for r in rows]


@router.get("/api/violations/{violation_id}")
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Violation not found")
    return _serialize_violation(v)


@router.delete("/api/violations")
def clear_violations(db: Session = Depends(get_db)):
    db.query(Violation).delete()
    db.commit()
    return {"status": "ok", "message": "All violations deleted"}
