import json
from datetime import date as _date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Union, Literal

from db.database import get_db
from db.models import Violation

router = APIRouter()


def _to_datetime(value: Union[datetime, _date, None]) -> Optional[datetime]:
    """Coerce a possibly-bare date (`YYYY-MM-DD`, what the frontend's date
    inputs emit) into a `datetime` at midnight. Accepts `None` and an
    already-typed `datetime` so callers can mix the two."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())


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
        "review_status": row.review_status,
        "acknowledged_at": row.acknowledged_at,
        "escalated_at": row.escalated_at,
        "archived_at": row.archived_at,
        "mask_assessment": row.mask_assessment,
        "bbox": _safe_json_load(row.bbox, None),
        "detections": _safe_json_load(row.detections, []),
    }


@router.get("/api/violations")
def get_violations(
    # Pagination — accept both shapes so the existing `limit/offset` callers
    # (and the redesigned frontend that uses `page/per_page`) keep working.
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    # Date range — accept either the native `start_date/end_date` names or
    # the shorter `date_from/date_to` aliases the frontend uses. Typed as
    # `date` (not `datetime`) so a bare `YYYY-MM-DD` from the frontend's
    # date inputs parses cleanly; full ISO datetimes are also accepted by
    # FastAPI's `date` coercion. `_to_datetime` normalises both shapes.
    start_date: Optional[_date] = None,
    end_date: Optional[_date] = None,
    date_from: Optional[_date] = None,
    date_to: Optional[_date] = None,
    # Other filters
    camera_id: Optional[int] = None,
    violation_type: Optional[str] = None,
    archived: bool = False,
    review_status: Optional[Literal["open", "acknowledged", "escalated"]] = None,
    db: Session = Depends(get_db)
):
    """
    List violations. Optional filters:
      - page / per_page               — 1-indexed pagination. When `page` is
                                        supplied, `limit`/`offset` are
                                        ignored and `per_page` defaults to 50.
      - start_date / end_date         — inclusive ISO datetimes (Phase 1)
      - date_from / date_to           — aliases for the two above (frontend)
      - camera_id                     — matches `source = "camera:{id}"`
      - violation_type                — substring match on `violation_type`
                                        (rows store "Missing: Helmet, ...").
                                        Pass `None` to disable.

    Returns `{items, total, page, per_page}` when paginated, otherwise a flat
    array (legacy callers). The dashboard default is `limit=50` with no page,
    so existing consumers that read `Array.isArray(...)` keep working.
    """
    # Resolve the date filter from either name pair.
    eff_start = _to_datetime(start_date or date_from)
    # Treat the `to` end of the range as end-of-day so a user typing
    # `2026-08-09` doesn't lose everything after midnight. The frontend's
    # date inputs only emit `YYYY-MM-DD`, so without this adjustment the
    # inclusive range covers 0 seconds of the chosen day.
    eff_end_date = end_date or date_to
    eff_end = (
        datetime.combine(eff_end_date, datetime.max.time())
        if eff_end_date is not None
        else None
    )

    base = db.query(Violation)
    base = base.filter(Violation.archived_at.isnot(None) if archived else Violation.archived_at.is_(None))
    if review_status:
        base = base.filter(Violation.review_status == review_status)
    if eff_start:
        base = base.filter(Violation.timestamp >= eff_start)
    if eff_end:
        base = base.filter(Violation.timestamp <= eff_end)
    if camera_id is not None:
        base = base.filter(Violation.source == f"camera:{camera_id}")
    if violation_type:
        # Substring match so "Helmet" matches "Missing: Helmet, Safety Vest".
        base = base.filter(Violation.violation_type.ilike(f"%{violation_type}%"))

    # Compute total BEFORE applying pagination so the response can include it.
    total = base.count()

    if page is not None:
        # 1-indexed. Clamp per_page to a sane range so a bad client can't
        # ask for a million rows.
        page = max(1, page)
        per_page = max(1, min(per_page or 50, 200))
        offset = (page - 1) * per_page
        limit = per_page
        rows = (
            base.order_by(Violation.timestamp.desc(), Violation.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [_serialize_violation(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    # No `page` supplied → legacy flat-array response.
    rows = base.order_by(Violation.timestamp.desc(), Violation.id.desc()).offset(offset).limit(limit).all()
    return [_serialize_violation(r) for r in rows]


class ReviewUpdate(BaseModel):
    action: Literal["acknowledge", "escalate", "archive"]


@router.patch("/api/violations/{violation_id}")
def review_violation(violation_id: int, update: ReviewUpdate, db: Session = Depends(get_db)):
    row = db.query(Violation).filter(Violation.id == violation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if update.action == "archive":
        row.archived_at = row.archived_at or now
    elif update.action == "acknowledge":
        row.acknowledged_at = row.acknowledged_at or now
        if row.review_status != "escalated":
            row.review_status = "acknowledged"
    elif update.action == "escalate":
        row.escalated_at = row.escalated_at or now
        row.review_status = "escalated"
    db.commit()
    db.refresh(row)
    return _serialize_violation(row)


@router.get("/api/violations/{violation_id}")
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Violation not found")
    return _serialize_violation(v)


@router.get('/api/violations/{violation_id}/preview/email')
def preview_violation_email(violation_id: int, db: Session = Depends(get_db)):
    from alerts.email_service import preview_email
    row = db.query(Violation).filter(Violation.id == violation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail='Violation not found')
    try:
        return preview_email(_serialize_violation(row))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/api/violations")
def clear_violations(db: Session = Depends(get_db)):
    raise HTTPException(status_code=405, detail="Violation deletion is disabled. Archive evidence instead.")


# ── Manual WhatsApp Share ─────────────────────────────────────────────────────

class WhatsAppShareRequest(BaseModel):
    """Body for the manual WhatsApp share endpoint.

    `phone_number` is optional — when omitted the backend falls back to the
    globally configured `ALERT_WHATSAPP_TO`. Including it lets the admin send
    the violation to any number without changing global settings.
    """
    phone_number: Optional[str] = None


@router.post("/api/violations/{violation_id}/share/whatsapp")
async def share_violation_whatsapp(
    violation_id: int,
    body: WhatsAppShareRequest = WhatsAppShareRequest(),
    db: Session = Depends(get_db),
):
    """Manually send a specific violation's details to WhatsApp.

    This endpoint bypasses the global `ENABLE_WHATSAPP_ALERTS` toggle so
    the admin can always dispatch a manual share regardless of whether
    automatic live-detection alerts are enabled. The process-level preview
    switch still blocks delivery. Live delivery requires configured Twilio credentials.

    Returns `{ok, message, transport}` matching the shape of the test alert
    response so the frontend can surface the same feedback UI.
    """
    from alerts.alert_manager import share_whatsapp
    row = db.query(Violation).filter(Violation.id == violation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    return await share_whatsapp(_serialize_violation(row), to_number=body.phone_number or None)
