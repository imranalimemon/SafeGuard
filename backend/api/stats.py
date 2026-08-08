import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from db.database import get_db
from db.models import Violation
from api.violations import _serialize_violation

router = APIRouter()

@router.get("/api/stats/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_violations = db.query(Violation).count()

    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_violations = db.query(Violation).filter(Violation.timestamp >= today_start).count()

    # ── Honest "0" instead of fake mock data ──
    # The DB only stores VIOLATION records, not a log of every detected person.
    # Producing `total_persons_detected = total_violations * 2` was a placeholder
    # that made compliance_rate meaningless. Real person counting requires a
    # detection-event log table (out of scope for the Core Fixes milestone).
    total_persons_detected = 0
    compliance_rate = 0.0

    recent_violations_rows = db.query(Violation).order_by(Violation.timestamp.desc()).limit(5).all()
    recent_violations = [_serialize_violation(r) for r in recent_violations_rows]

    # Calculate violations by type
    all_violations = db.query(Violation).all()
    violations_by_type = {"Helmet": 0, "Face Mask": 0, "Safety Vest": 0}
    avg_conf = 0.0

    if all_violations:
        total_conf = sum(v.confidence for v in all_violations if v.confidence)
        avg_conf = total_conf / len(all_violations)
        for v in all_violations:
            for ppe in ["Helmet", "Face Mask", "Safety Vest"]:
                if v.missing_ppe and ppe in v.missing_ppe:
                    violations_by_type[ppe] += 1

    return {
        "total_violations": total_violations,
        "today_violations": today_violations,
        "total_persons_detected": total_persons_detected,
        "compliance_rate": compliance_rate,
        "avg_confidence": avg_conf,
        "violations_by_type": violations_by_type,
        "recent_violations": recent_violations,
    }
