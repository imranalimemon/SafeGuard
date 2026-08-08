import asyncio
import logging
from db.database import SessionLocal
from db.models import AlertLog
from alerts.throttle import throttle
from alerts.email_service import send_email_alert
from alerts.whatsapp_service import send_whatsapp_alert
from config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

async def trigger_alerts(violation_data, screenshot_path=None):
    tasks = []
    
    # Check email throttle
    if settings.ENABLE_EMAIL_ALERTS and throttle.can_send("email", settings.EMAIL_COOLDOWN_SECONDS):
        throttle.record_sent("email")
        tasks.append(send_and_log(send_email_alert, "email", violation_data, screenshot_path))
        
    # Check whatsapp throttle
    if settings.ENABLE_WHATSAPP_ALERTS and throttle.can_send("whatsapp", settings.WHATSAPP_COOLDOWN_SECONDS):
        throttle.record_sent("whatsapp")
        tasks.append(send_and_log(send_whatsapp_alert, "whatsapp", violation_data))
        
    if tasks:
        await asyncio.gather(*tasks)

async def send_and_log(send_func, channel, violation_data, screenshot_path=None):
    try:
        if channel == "email":
            success = await send_func(violation_data, screenshot_path)
        else:
            success = await send_func(violation_data)
            
        status = "success" if success else "failed"
        log_alert(channel, status, violation_data.get('id') if isinstance(violation_data, dict) else None)
    except Exception as e:
        logger.error(f"Failed to send {channel} alert: {str(e)}")
        log_alert(channel, "error", violation_data.get('id') if isinstance(violation_data, dict) else None)

def log_alert(channel: str, status: str, violation_id: int = None):
    db = SessionLocal()
    try:
        log = AlertLog(
            sent_at=datetime.utcnow(),
            channel=channel,
            status=status,
            violation_id=violation_id
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log alert to DB: {str(e)}")
    finally:
        db.close()
