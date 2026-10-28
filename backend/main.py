"""
SafeGuard AI — FastAPI Main Application
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os, sys, logging

logger = logging.getLogger("uvicorn.error")

# Ensure backend dir is in path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from db.database import engine, Base, ensure_violation_columns, ensure_alert_settings_columns, ensure_alert_log_columns, SessionLocal
from db.models import AlertSettings
from db import models as db_models
from runtime_settings import restore_settings
from starlette.concurrency import run_in_threadpool
from api import health, upload, violations, stats
from api import settings as api_settings
from api import cameras
from websocket.manager import router as websocket_router
from security import AuthService, AccessMiddleware, router as auth_router
from evidence import router as evidence_router

auth_service = AuthService(SessionLocal, db_models, settings)


def initialize_storage():
    Base.metadata.create_all(bind=engine)
    ensure_violation_columns(engine)
    ensure_alert_settings_columns(engine)
    ensure_alert_log_columns(engine)
    from sqlalchemy import text
    with engine.connect() as connection:
        demo = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='demo_metadata'")).first()
        settings.DEMO_LABEL = connection.execute(text('SELECT label FROM demo_metadata LIMIT 1')).scalar() if demo else None


@asynccontextmanager
async def lifespan(app):
    from logging_setup import configure_logging
    app.state.log_handler = configure_logging(settings)
    await run_in_threadpool(initialize_storage)
    await startup_event()
    await run_in_threadpool(auth_service.bootstrap)
    try:
        yield
    finally:
        await shutdown_event()

app = FastAPI(
    title="SafeGuard AI API",
    description="Real-time PPE Detection & Safety Compliance System",
    version="1.0.0", lifespan=lifespan, debug=False
)
app.state.auth = auth_service
app.add_middleware(AccessMiddleware, service=auth_service)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

# Ensure dirs exist
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)

# Evidence routes are protected by the same session middleware as the API.
app.include_router(auth_router)
app.include_router(evidence_router)
from api.system import router as system_router
app.include_router(system_router)

# Include routers
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(violations.router)
app.include_router(stats.router)
app.include_router(api_settings.router)
app.include_router(cameras.router)
app.include_router(websocket_router)

async def startup_event():
    await run_in_threadpool(restore_settings, SessionLocal, AlertSettings, settings)
    print("=" * 50)
    print("  SafeGuard AI API -- Starting Up")
    print("=" * 50)
    print(f"  Model path:      {settings.MODEL_PATH}")
    print(f"  Database:        {settings.DATABASE_URL}")
    print(f"  Email alerts:    {'ON' if settings.ENABLE_EMAIL_ALERTS else 'OFF'}")
    print(f"  WhatsApp alerts: {'ON' if settings.ENABLE_WHATSAPP_ALERTS else 'OFF'}")
    print(f"  Alert delivery:  {settings.ALERT_DELIVERY_MODE} (DB toggles cannot change this)")
    print(f"  Screenshots:     {settings.SCREENSHOT_DIR}")
    if settings.ALERT_DEBUG_MODE:
        print(f"  Alert debug:     ON  -> {settings.DEBUG_SMTP_HOST}:{settings.DEBUG_SMTP_PORT}, log={settings.DEBUG_LOG_FILE}")
        print('  Debug alerts use preview only; no SMTP/Twilio connection is opened.')
    else:
        print(f"  Alert debug:     OFF")
    print("=" * 50)


async def shutdown_event():
    from websocket.registry import shutdown
    await shutdown()
    await run_in_threadpool(engine.dispose)
    handler = getattr(app.state, 'log_handler', None)
    if handler:
        logging.getLogger().removeHandler(handler)
        handler.close()


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Pydantic's input/context fields can echo passwords and other secret values.
    return JSONResponse({'detail': [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']}
                                    for e in exc.errors()]}, status_code=422)


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logger.error('Request failed: %s', type(exc).__name__, exc_info=True)
    return JSONResponse({'detail': 'The request failed. Check the system log and retry.'}, status_code=500)

@app.get("/")
async def root():
    return {"name": "SafeGuard AI", "version": "1.0.0", "status": "running"}
