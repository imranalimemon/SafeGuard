from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime
from db.database import Base

class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
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

class AlertLog(Base):
    __tablename__ = "alert_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(Integer, ForeignKey("violations.id"))
    channel = Column(String) # 'email' or 'whatsapp'
    sent_to = Column(String)
    sent_at = Column(DateTime)
    status = Column(String) # 'success' or 'failed'
