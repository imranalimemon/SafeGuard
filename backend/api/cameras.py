"""
Cameras CRUD router.

Phase 2 Slice 2 — multi-camera management.

Endpoints
---------
GET    /api/cameras                 list all cameras
POST   /api/cameras                 create a camera (no auth guard at this
                                   milestone; Phase 3 will add JWT)
GET    /api/cameras/{id}            fetch a single camera
PUT    /api/cameras/{id}            partial update (any subset of fields)
DELETE /api/cameras/{id}            delete a camera
POST   /api/cameras/{id}/test       try to open the capture; return ok/error

Validation lives in Pydantic schemas (`CameraCreate`, `CameraUpdate`). The
webcam-vs-ip-vs-rtsp distinction is enforced by `source_type` + `url` rules.
"""
from typing import List, Optional

import asyncio
import cv2
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Camera

router = APIRouter()

VALID_SOURCE_TYPES = {"ip", "rtsp", "webcam"}


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    source_type: str = Field(..., description="'ip' | 'rtsp' | 'webcam'")
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    enabled: bool = True

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, v: str) -> str:
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}")
        return v


class CameraUpdate(BaseModel):
    """Partial update — every field optional. Same validators apply when present."""

    name: Optional[str] = None
    source_type: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}")
        return v


class CameraOut(BaseModel):
    id: int
    name: str
    source_type: str
    url: Optional[str]
    username: Optional[str]
    location: Optional[str]
    enabled: bool
    created_at: Optional[str]

    class Config:
        from_attributes = True


def _serialize(c: Camera) -> dict:
    """CameraOut with `created_at` rendered as ISO string (matches ViolationOut style)."""
    return {
        "id": c.id,
        "name": c.name,
        "source_type": c.source_type,
        "url": c.url,
        "username": c.username,
        "password": c.password,  # included for completeness in this FYP; UI should mask it
        "location": c.location,
        "enabled": c.enabled,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _validate_url_for_source(body: dict) -> None:
    """`url` is required for ip/rtsp, optional for webcam (defaults to '0')."""
    src = body.get("source_type")
    url = body.get("url")
    if src in ("ip", "rtsp") and not url:
        raise HTTPException(status_code=422, detail=f"url is required for source_type={src}")
    if src == "webcam" and not url:
        body["url"] = "0"


@router.get("/api/cameras")
def list_cameras(db: Session = Depends(get_db)) -> List[dict]:
    rows = db.query(Camera).order_by(Camera.id.asc()).all()
    return [_serialize(c) for c in rows]


@router.post("/api/cameras", status_code=201)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> dict:
    data = payload.model_dump()
    _validate_url_for_source(data)
    if db.query(Camera).filter(Camera.name == data["name"]).first():
        raise HTTPException(status_code=409, detail=f"Camera name '{data['name']}' already exists")
    cam = Camera(**data)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return _serialize(cam)


@router.get("/api/cameras/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _serialize(cam)


@router.put("/api/cameras/{camera_id}")
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)) -> dict:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _serialize(cam)
    # Re-validate url/source_type if either changed.
    merged = {**{c.name: getattr(cam, c.name) for c in cam.__table__.columns}, **data}
    _validate_url_for_source(merged)
    for k, v in data.items():
        setattr(cam, k, v)
    db.commit()
    db.refresh(cam)
    return _serialize(cam)


@router.delete("/api/cameras/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.delete(cam)
    db.commit()
    return {"status": "ok", "deleted_id": camera_id}


async def _try_open(camera: Camera) -> dict:
    """Open cv2.VideoCapture in a thread to avoid blocking the event loop."""

    def _open():
        url = camera.url or "0"
        # Webcam rows store the index as a string ("0", "1", ...); cv2 wants int.
        if camera.source_type == "webcam":
            cap = cv2.VideoCapture(int(url) if url.isdigit() else 0)
        else:
            if camera.username and camera.password and "://" in url and "@" not in url.split("://", 1)[1]:
                scheme, rest = url.split("://", 1)
                url = f"{scheme}://{camera.username}:{camera.password}@{rest}"
            cap = cv2.VideoCapture(url)
        try:
            ok = cap.isOpened()
            return ok
        finally:
            cap.release()

    ok = await asyncio.get_event_loop().run_in_executor(None, _open)
    if ok:
        return {"ok": True, "message": f"Camera '{camera.name}' opened successfully"}
    return {"ok": False, "message": f"Could not open camera '{camera.name}'. Check the URL/index."}


@router.post("/api/cameras/{camera_id}/test")
async def test_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return await _try_open(cam)