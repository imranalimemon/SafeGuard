from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from db.database import get_db
from db.models import Violation

router = APIRouter()

@router.get("/api/stats/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_violations = db.query(Violation).count()
    
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_violations = db.query(Violation).filter(Violation.timestamp >= today_start).count()
    
    # Just an estimation if we only store violations.
    # We should return what we can
    total_persons_detected = total_violations * 2 # Mock data for persons since DB only stores violations
    compliance_rate = 0.0
    if total_persons_detected > 0:
        compliance_rate = ((total_persons_detected - total_violations) / total_persons_detected) * 100
    
    recent_violations = db.query(Violation).order_by(Violation.timestamp.desc()).limit(5).all()
    
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
        "recent_violations": recent_violations
    }
