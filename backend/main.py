"""
SafeGuard AI — FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, sys

# Ensure backend dir is in path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from db.database import engine, Base
from api import health, upload, violations, stats
from api import settings as api_settings
from websocket.manager import router as websocket_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SafeGuard AI API",
    description="Real-time PPE Detection & Safety Compliance System",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure dirs exist
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)

# Serve screenshots
app.mount("/screenshots", StaticFiles(directory=settings.SCREENSHOT_DIR), name="screenshots")

# Include routers
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(violations.router)
app.include_router(stats.router)
app.include_router(api_settings.router)
app.include_router(websocket_router)

@app.on_event("startup")
async def startup_event():
    print("=" * 50)
    print("  SafeGuard AI API -- Starting Up")
    print("=" * 50)
    print(f"  Model path:      {settings.MODEL_PATH}")
    print(f"  Database:        {settings.DATABASE_URL}")
    print(f"  Email alerts:    {'ON' if settings.ENABLE_EMAIL_ALERTS else 'OFF'}")
    print(f"  WhatsApp alerts: {'ON' if settings.ENABLE_WHATSAPP_ALERTS else 'OFF'}")
    print(f"  Screenshots:     {settings.SCREENSHOT_DIR}")
    print("=" * 50)

@app.get("/")
async def root():
    return {"name": "SafeGuard AI", "version": "1.0.0", "status": "running"}
