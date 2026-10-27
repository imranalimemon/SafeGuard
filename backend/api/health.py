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
    return {
        "status": "ok" if model_loaded and db_connected else "degraded",
        "model_loaded": model_loaded,
        "db_connected": db_connected,
        "model_name": model_name,
        "execution_providers": providers,
        "email_enabled": settings.ENABLE_EMAIL_ALERTS,
        "whatsapp_enabled": settings.ENABLE_WHATSAPP_ALERTS
    }
