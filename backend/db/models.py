from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime
from db.database import Base


class AdminUser(Base):
    __tablename__ = 'admin_users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('admin_users.id'), nullable=False)
    expires_at = Column(DateTime, nullable=False)

class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    violation_type = Column(String)
    person_count = Column(Integer)
    violation_count = Column(Integer)
    screenshot_path = Column(String)
    confidence = Column(Float)
    alert_sent = Column(Boolean, default=False)
    missing_ppe = Column(String)
    details = Column(String)

    # ── Enriched columns (added in Core Fixes milestone) ──
    # `bbox`          — JSON-text primary person bounding box, [x1, y1, x2, y2]
    # `detections`    — JSON-text full detection list for the violating frame
    # `source`        — "image_upload" | "video_upload" | "live_stream"
    # All are nullable so legacy rows from before this migration remain valid.
    bbox = Column(String, nullable=True)
    detections = Column(String, nullable=True)
    source = Column(String, nullable=True)
    review_status = Column(String, nullable=False, default="open", server_default="open")
    acknowledged_at = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    mask_assessment = Column(String, nullable=True)

class AlertSettings(Base):
    __tablename__ = "alert_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    email_enabled = Column(Boolean, default=False)
    whatsapp_enabled = Column(Boolean, default=False)
    email_recipients = Column(String)
    whatsapp_recipient = Column(String)
    email_cooldown = Column(Integer, default=30)
    whatsapp_cooldown = Column(Integer, default=60)
    confidence_threshold = Column(Float, default=0.5)
    required_ppe = Column(String, nullable=True)
    frame_skip = Column(Integer, nullable=True)

class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id"))
    channel = Column(String) # 'email' or 'whatsapp'
    sent_to = Column(String)
    sent_at = Column(DateTime)
    status = Column(String) # 'success' or 'failed'
    message = Column(String, nullable=True)
    transport = Column(String, nullable=True)


class Camera(Base):
    """
    Camera configuration. One row per physical feed.

    `source_type` is constrained at the application layer to:
        'ip'     — RTSP/HTTP stream, requires `url`
        'rtsp'   — RTSP stream, requires `url`
        'webcam' — local webcam index, `url` stores the integer as a string
                    (e.g. "0" for /dev/video0 on Linux, the first camera on
                    Windows). Defaults to "0" when omitted.

    Violations produced by a camera are stored in the `violations` table with
    `source = f"camera:{camera.id}"`. No FK is added — string-encoding keeps
    the migration trivial and matches the pattern used by image/video uploads.

    Network URLs and credentials are encrypted with the deployment Fernet key.
    API serialization omits credentials and URL query tokens.
    """
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    source_type = Column(String, nullable=False)  # 'ip' | 'rtsp' | 'webcam'
    url = Column(String, nullable=True)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    location = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))


class WorkerObservation(Base):
    __tablename__ = 'worker_observations'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    source = Column(String, nullable=False, index=True)
    workers = Column(Integer, nullable=False)
    compliant = Column(Integer, nullable=False)
    violating = Column(Integer, nullable=False)
    unknown = Column(Integer, nullable=False)
    mask_unknown = Column(Integer, nullable=False)
