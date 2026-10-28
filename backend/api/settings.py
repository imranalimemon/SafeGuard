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
    return result


@router.get('/api/settings/alerts/preview-email')
def preview_test_email():
    from alerts.email_service import preview_email
    from alerts.alert_manager import _synthetic_violation
    return preview_email(_synthetic_violation())

# Environment gate plus a deliberate operator confirmation; never persisted in DB.
from typing import Literal
from pydantic import BaseModel
from fastapi import HTTPException

class DeliveryUpdate(BaseModel):
    mode: Literal['preview', 'live']
    confirmation: str = ''

@router.get('/api/settings/alerts/delivery')
def delivery_status():
    from alerts.content import preview_only
    return {'deployment_mode': settings.ALERT_DELIVERY_MODE,
            'effective_mode': 'preview' if preview_only() else 'live',
            'can_go_live': settings.ALERT_DELIVERY_MODE == 'live' and not settings.ALERT_DEBUG_MODE,
            'explanation': 'Live delivery requires ALERT_DELIVERY_MODE=live at startup and explicit confirmation for this process. A restart returns to unconfirmed preview.'}

@router.post('/api/settings/alerts/delivery')
def change_delivery(value: DeliveryUpdate):
    if value.mode == 'preview':
        settings.ALERT_LIVE_CONFIRMED = False
        return delivery_status()
    if settings.ALERT_DELIVERY_MODE != 'live' or settings.ALERT_DEBUG_MODE:
        raise HTTPException(409, 'This process is restricted to preview. Configure ALERT_DELIVERY_MODE=live before startup to permit confirmation.')
    if value.confirmation != 'ENABLE LIVE ALERTS':
        raise HTTPException(422, 'Type ENABLE LIVE ALERTS to confirm configured recipients may receive real messages.')
    if not settings.ENABLE_EMAIL_ALERTS and not settings.ENABLE_WHATSAPP_ALERTS:
        raise HTTPException(422, 'Enable and save at least one alert channel first.')
    if settings.ENABLE_EMAIL_ALERTS:
        from alerts.email_service import smtp_configuration
        status=smtp_configuration()
        if not status['configured']:raise HTTPException(422,status['error'])
    settings.ALERT_LIVE_CONFIRMED = True
    return delivery_status()
