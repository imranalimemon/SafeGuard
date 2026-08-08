from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from db.database import get_db
from db.models import Violation

router = APIRouter()

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
    return query.order_by(Violation.timestamp.desc()).offset(offset).limit(limit).all()

@router.get("/api/violations/{violation_id}")
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Violation not found")
    return v

@router.delete("/api/violations")
def clear_violations(db: Session = Depends(get_db)):
    db.query(Violation).delete()
    db.commit()
    return {"status": "ok", "message": "All violations deleted"}
