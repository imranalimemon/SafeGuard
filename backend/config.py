"""
SafeGuard AI — Configuration
Reads all settings from .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # ── App ──
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    ALLOWED_ORIGINS: list = [value.strip().rstrip('/') for value in os.getenv(
        "ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(',') if value.strip()]
    if not ALLOWED_ORIGINS or any('*' in origin or not origin.startswith(('http://', 'https://')) for origin in ALLOWED_ORIGINS):
        raise ValueError('ALLOWED_ORIGINS must contain explicit HTTP(S) frontend origins.')
    ADMIN_USERNAME: str = os.getenv('SAFEGUARD_ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD: str = os.getenv('SAFEGUARD_ADMIN_PASSWORD', '')
    CREDENTIAL_KEY: str = os.getenv('SAFEGUARD_CREDENTIAL_KEY', '')
    COOKIE_SECURE: bool = os.getenv('SAFEGUARD_COOKIE_SECURE', 'false').lower() == 'true'

    # ── Model ──
    MODEL_PATH: str = os.getenv("MODEL_PATH", "best.onnx")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.45"))
    # Inference sampling only; does not change detector thresholds or PPE rules.
    STREAM_DETECTION_INTERVAL: int = max(1, int(os.getenv("STREAM_DETECTION_INTERVAL", "3")))
    VIOLATION_IOU_THRESHOLD: float = float(os.getenv("VIOLATION_IOU_THRESHOLD", "0.3"))
    NUM_CLASSES: int = int(os.getenv("NUM_CLASSES", "4"))
    CLASS_NAMES: dict = {
        0: "Face Mask",
        1: "Helmet",
        2: "Person",
        3: "Safety Vest",
    }
    PERSON_CLASS_ID: int = 2
    PPE_CLASS_IDS: list = [0, 1, 3]

    # ── Violation rules ──
    # Default policy covers all three objectives. Saved site policy is restored
    # from the DB at startup; legacy REQUIRED_PPE environment values are ignored.
    REQUIRED_PPE: list = ["Helmet", "Safety Vest", "Face Mask"]
    MASK_MIN_PERSON_WIDTH: int = 100
    MASK_MIN_PERSON_HEIGHT: int = 160

    # Per-class IoU thresholds for PPE → person association. Smaller objects
    # (face masks) need a tighter threshold because their bounding boxes are
    # smaller and partial overlap is still meaningful coverage.
    VIOLATION_IOU_THRESHOLDS: dict = {
        "Face Mask":   float(os.getenv("FACE_MASK_IOU_THRESHOLD",   "0.2")),
        "Helmet":      float(os.getenv("HELMET_IOU_THRESHOLD",      "0.3")),
        "Safety Vest": float(os.getenv("VEST_IOU_THRESHOLD",        "0.3")),
    }

    # Cooldown window (seconds) for the violation deduplicator. After a
    # violation of (source, missing_ppe) is logged, subsequent identical
    # violations within this window are suppressed. Resets on backend restart.
    VIOLATION_COOLDOWN_SECONDS: int = int(os.getenv("VIOLATION_COOLDOWN_SECONDS", "10"))

    # ── Database ──
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./safeguard.db")

    # ── Email Alerts ──
    # Process-only safety switch: DB alert toggles cannot enable live delivery.
    ALERT_DELIVERY_MODE: str = os.getenv("ALERT_DELIVERY_MODE", "preview").lower()
    if ALERT_DELIVERY_MODE not in {"preview", "live"}:
        raise ValueError("ALERT_DELIVERY_MODE must be preview or live")
    ALERT_TIMEZONE: str = os.getenv("ALERT_TIMEZONE", "Asia/Karachi")
    ALERT_NETWORK_TIMEOUT_SECONDS: float = float(os.getenv("ALERT_NETWORK_TIMEOUT_SECONDS", "10"))
    if not 0 < ALERT_NETWORK_TIMEOUT_SECONDS <= 60:
        raise ValueError("ALERT_NETWORK_TIMEOUT_SECONDS must be greater than 0 and at most 60")
    ENABLE_EMAIL_ALERTS: bool = os.getenv("ENABLE_EMAIL_ALERTS", "false").lower() == "true"
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    ALERT_EMAIL_FROM: str = os.getenv("ALERT_EMAIL_FROM", "")
    ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")
    EMAIL_COOLDOWN_SECONDS: int = int(os.getenv("EMAIL_COOLDOWN_SECONDS", "30"))

    # ── WhatsApp Alerts ──
    ENABLE_WHATSAPP_ALERTS: bool = os.getenv("ENABLE_WHATSAPP_ALERTS", "false").lower() == "true"
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    ALERT_WHATSAPP_TO: str = os.getenv("ALERT_WHATSAPP_TO", "")
    WHATSAPP_COOLDOWN_SECONDS: int = int(os.getenv("WHATSAPP_COOLDOWN_SECONDS", "60"))

    # ── Storage ──
    SCREENSHOT_DIR: str = os.getenv("SCREENSHOT_DIR", "./screenshots")
    MAX_IMAGE_UPLOAD_BYTES: int = int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    MAX_VIDEO_UPLOAD_BYTES: int = int(os.getenv("MAX_VIDEO_UPLOAD_BYTES", str(100 * 1024 * 1024)))
    MAX_IMAGE_PIXELS: int = 25_000_000

    # ── Debug / development ──
    # When true, alerts are routed through `alerts.debug_receiver` instead of
    # real SMTP / Twilio. Lets us verify the full pipeline end-to-end without
    # external accounts. NEVER enable in production.
    ALERT_DEBUG_MODE: bool = os.getenv("ALERT_DEBUG_MODE", "false").lower() == "true"
    DEBUG_SMTP_HOST: str = os.getenv("DEBUG_SMTP_HOST", "127.0.0.1")
    DEBUG_SMTP_PORT: int = int(os.getenv("DEBUG_SMTP_PORT", "1025"))
    DEBUG_LOG_FILE: str = os.getenv("DEBUG_LOG_FILE", "./.alert-debug.log")

    # ── Colors for visualization ──
    CLASS_COLORS: dict = {
        "Face Mask":   (255, 107, 107),
        "Helmet":      (78, 205, 196),
        "Person":      (69, 183, 209),
        "Safety Vest": (255, 160, 122),
    }
    COMPLIANT_COLOR = (0, 255, 136)   # #00FF88
    VIOLATION_COLOR = (51, 51, 255)   # #FF3333 in BGR


settings = Settings()

# Create screenshot directory
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)
