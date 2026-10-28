from fastapi import APIRouter
from pathlib import Path
from sqlalchemy import text
from config import settings
from db.database import engine
from detection.model import get_detector

router = APIRouter()

@router.get("/api/health")
def health():
    model_name = None
    providers = []
    try:
        detector = get_detector()
        providers = detector.session.get_providers()
        model_name = Path(detector.model_path).name
    except Exception:
        pass

    db_connected = False
    try:
        with engine.connect() as connection:
            db_connected = connection.execute(text("SELECT 1")).scalar() == 1
    except Exception:
        pass

    model_loaded = bool(providers)
    smtp = {'configured': None, 'error': None}
    if settings.ENABLE_EMAIL_ALERTS:
        from alerts.email_service import smtp_configuration
        smtp = smtp_configuration()  # Configuration only: no connection/login/send.
    return {
        "status": "ok" if model_loaded and db_connected else "degraded",
        "model_loaded": model_loaded,
        "db_connected": db_connected,
        "model_name": model_name,
        "execution_providers": providers,
        "email_enabled": settings.ENABLE_EMAIL_ALERTS,
        "whatsapp_enabled": settings.ENABLE_WHATSAPP_ALERTS,
        "alert_delivery_mode": 'preview' if settings.ALERT_DEBUG_MODE else ('live' if settings.ALERT_DELIVERY_MODE == 'live' and getattr(settings, 'ALERT_LIVE_CONFIRMED', True) else 'preview'),
        "smtp_configured": smtp['configured'],
        "smtp_configuration_error": smtp['error'],
        "smtp_status_note": 'Configuration check only; network reachability and authentication are not tested.',
    }
