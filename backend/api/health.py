from fastapi import APIRouter
from config import settings

router = APIRouter()

@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": True,
        "db_connected": True,
        "email_enabled": settings.ENABLE_EMAIL_ALERTS,
        "whatsapp_enabled": settings.ENABLE_WHATSAPP_ALERTS
    }
