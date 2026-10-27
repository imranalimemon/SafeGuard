import logging
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import AlertSettings
from config import settings
from runtime_settings import SavedSettings as AlertSettingsUpdate, read_settings, apply_settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/settings/alerts")
def get_alert_settings(db: Session = Depends(get_db)):
    row = db.query(AlertSettings).order_by(AlertSettings.id).first()
    return read_settings(row, settings).model_dump()


@router.put("/api/settings/alerts")
def update_alert_settings(update_data: AlertSettingsUpdate, db: Session = Depends(get_db)):
    row = db.query(AlertSettings).order_by(AlertSettings.id).first()
    if row is None:
        row = AlertSettings()
        db.add(row)
    for key, value in update_data.model_dump().items():
        setattr(row, key, json.dumps(value) if key == 'required_ppe' else value)
    db.commit()
    apply_settings(update_data, settings)
    return update_data.model_dump()


@router.post("/api/settings/alerts/test-email")
async def test_email_alert():
    """Send a test email through the same code path as a real violation.
    Returns {ok, message, transport}. Bypasses cooldown so the operator
    can re-trigger at will."""
    from alerts.alert_manager import trigger_alerts_test
    if not settings.ENABLE_EMAIL_ALERTS:
        return {
            "ok": False,
            "message": "Email alerts are disabled in Settings — enable them first.",
            "transport": "none",
        }
    try:
        result = await trigger_alerts_test("email")
    except Exception as e:
        logger.exception("[api.settings] test email failed")
        return {"ok": False, "message": f"Failed: {e}", "transport": "none"}
    if result["transport"] == "debug":
        result["message"] = "Sent via local debug receiver — check the alert debug log."
    return result


@router.post("/api/settings/alerts/test-whatsapp")
async def test_whatsapp_alert():
    """Send a test WhatsApp message through the same code path as a real
    violation. Returns {ok, message, transport}. Bypasses cooldown."""
    from alerts.alert_manager import trigger_alerts_test
    if not settings.ENABLE_WHATSAPP_ALERTS:
        return {
            "ok": False,
            "message": "WhatsApp alerts are disabled in Settings — enable them first.",
            "transport": "none",
        }
    try:
        result = await trigger_alerts_test("whatsapp")
    except Exception as e:
        logger.exception("[api.settings] test whatsapp failed")
        return {"ok": False, "message": f"Failed: {e}", "transport": "none"}
    if result["transport"] == "debug":
        result["message"] = "Sent via local debug receiver — check the alert debug log."
    return result
