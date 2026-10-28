from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from db.database import get_db
from db.models import Violation, WorkerObservation
from api.violations import _serialize_violation

router = APIRouter()

@router.get("/api/stats/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_violations = db.query(Violation).count()

    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    today_start = datetime.combine(today, datetime.min.time())
    today_violations = db.query(Violation).filter(Violation.timestamp >= today_start).count()

    # Violation-only storage has no denominator for historical worker totals or
    # compliance. Null means unavailable; live counts come from the WebSocket.
    total_persons_detected = None
    compliance_rate = None

    recent_violations_rows = db.query(Violation).filter(Violation.archived_at.is_(None)).order_by(Violation.timestamp.desc(), Violation.id.desc()).limit(5).all()
    recent_violations = [_serialize_violation(r) for r in recent_violations_rows]

    # Calculate violations by type
    all_violations = db.query(Violation).all()
    violations_by_type = {"Helmet": 0, "Face Mask": 0, "Safety Vest": 0}
    confidences = [v.confidence for v in all_violations if v.confidence is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else None

    if all_violations:
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

@router.get('/api/stats/analytics')
def analytics(db: Session = Depends(get_db)):
    from sqlalchemy import func
    by_day = [{'date': str(day), 'violations': count} for day,count in db.query(func.date(Violation.timestamp),func.count()).group_by(func.date(Violation.timestamp)).order_by(func.date(Violation.timestamp)).all()]
    by_camera = [{'source': source or 'Source not recorded', 'violations': count} for source,count in db.query(Violation.source,func.count()).group_by(Violation.source).all()]
    reviews = {status or 'open': count for status,count in db.query(Violation.review_status,func.count()).group_by(Violation.review_status).all()}
    types = {'Helmet':0,'Safety Vest':0,'Face Mask':0}
    for (missing,) in db.query(Violation.missing_ppe).all():
        for name in set(part.strip() for part in (missing or '').split(',')):
            if name in types: types[name]+=1
    trend=[]
    query=db.query(func.date(WorkerObservation.timestamp),func.sum(WorkerObservation.workers),func.sum(WorkerObservation.compliant),func.sum(WorkerObservation.violating),func.sum(WorkerObservation.unknown),func.count()).group_by(func.date(WorkerObservation.timestamp)).order_by(func.date(WorkerObservation.timestamp))
    for day,workers,compliant,violating,unknown,frames in query.all():
        denominator=compliant+violating
        trend.append({'date':str(day),'worker_observations':workers,'compliant':compliant,'violating':violating,'unknown':unknown,'frames_analyzed':frames,'assessed_denominator':denominator,'compliance_rate':round(compliant/denominator*100,2) if denominator else None})
    return {'violations_per_day':by_day,'violations_by_source':by_camera,'violations_by_type':types,'review_status_counts':reviews,'compliance_trend':trend,
            'note':'All recorded violations, including archived. Compliance counts sampled worker observations, not unique workers; unknown-only workers are excluded from its denominator. Historical records before observation storage have no compliance denominator.'}
