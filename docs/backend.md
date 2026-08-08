# SafeGuard AI — Backend Documentation

## Overview
The SafeGuard AI backend is a high-performance Python application built with FastAPI. It handles RESTful API requests, real-time WebSocket streaming, file uploads, asynchronous alert triggering, and orchestrates the YOLOv8 machine learning inference pipeline.

## Tech Stack
- **Web Framework:** FastAPI (with Uvicorn server)
- **Database ORM:** SQLAlchemy
- **Machine Learning:** Ultralytics (YOLOv8)
- **Image Processing:** OpenCV (`cv2`), NumPy
- **Environment Management:** `python-dotenv` for `.env` configurations

## Core Architecture
The backend is organized inside the `backend/` directory, following a clean, modular structure:

- `main.py`: The FastAPI application entry point. Configures CORS, mounts the static directory for serving screenshots, and registers all API routers and WebSocket endpoints.
- `config.py`: Centralized configuration management utilizing Pydantic (or simple os/dotenv loading). It loads variables like Database URLs, Alert credentials, API keys, and model paths from the `.env` file.
- `api/`: Contains all REST API route handlers (Controllers).
  - `health.py`: Basic API health check endpoints.
  - `upload.py`: Handles `multipart/form-data` uploads for static images and videos, routing them to the ML pipeline and saving results to the database.
  - `violations.py`: CRUD operations for accessing historical violation data (supports pagination and filtering).
  - `stats.py`: Aggregation endpoints for dashboard KPIs (e.g., total violations today, average compliance rate).
  - `settings.py`: Endpoints to get and update the system configuration (alert toggles, confidence thresholds) stored in the database.
- `websocket/manager.py`: Manages active WebSocket connections for the live camera feed, broadcasting annotated frames in real-time.
- `db/`: Database configuration and models (detailed in `database.md`).
- `detection/`: The ML pipeline (detailed in `ml-violations-alerts.md`).
- `alerts/`: Notification handlers (detailed in `ml-violations-alerts.md`).

## Request Lifecycle (Example: Image Upload)
1. **Client Request:** The React frontend sends an image via POST to `/api/upload/image`.
2. **API Router (`upload.py`):** The file is saved temporarily in `backend/temp/`.
3. **ML Pipeline (`detection/model.py`):** The image is read via OpenCV and passed to the YOLOv8 model for inference.
4. **Logic & Annotation:** The `violation_logic.py` determines if PPE is missing based on database settings. The `annotator.py` draws bounding boxes and violation overlays on the image.
5. **Storage:** The annotated image is saved to `backend/screenshots/`.
6. **Database Write:** If a violation is detected, a new record is inserted via SQLAlchemy.
7. **Alert Triggering:** The `alert_manager.py` checks cooldowns and dispatches email/WhatsApp notifications if necessary.
8. **Response:** A JSON payload containing bounding boxes, stats, and the annotated image URL is returned to the frontend.

## Environment Configuration
The backend relies heavily on a `.env` file for configuration:
```env
DATABASE_URL=sqlite:///./safeguard.db
MODEL_PATH=../models/yolov8s.pt
ENABLE_EMAIL_ALERTS=True
SMTP_SERVER=smtp.gmail.com
# ... other configurations
```

## Running the Server
```bash
# Start the FastAPI server with live-reloading
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
