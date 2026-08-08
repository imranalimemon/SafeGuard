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
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

    # ── Model ──
    MODEL_PATH: str = os.getenv("MODEL_PATH", "best.onnx")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.45"))
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

    # ── Database ──
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./safeguard.db")

    # ── Email Alerts ──
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
