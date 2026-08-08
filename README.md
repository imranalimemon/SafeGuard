# SafeGuard AI — PPE Detection & Safety Compliance System

SafeGuard AI is a startup-grade, professional real-time Personal Protective Equipment (PPE) detection and safety compliance dashboard designed for industrial workspaces. Built with a FastAPI backend and a Vite + React frontend, the system runs a custom-trained YOLOv8s model in ONNX format to detect personnel and check for safety helmet and high-visibility vest compliance.

---

## 🚀 Key Features

*   **Real-time YOLOv8s Inference:** Analyzes streams via WebSocket and detects:
    *   `Person`
    *   `Helmet`
    *   `Safety Vest`
    *   `Face Mask`
*   **Compliance Logic:** Compares overlap between detected workers and safety gear using Intersection-over-Union (IoU) thresholds to flags violations.
*   **Instant Notifications:** Sends alerts dynamically (email SMTP and WhatsApp via Twilio) when violations are detected, using smart cooldown throttle windows to prevent alert fatigue.
*   **Interactive Dashboard:** Displays real-time compliance rate, total worker count, recent violations feed, and active stream viewer.
*   **Manual Upload Analysis:** Upload images or videos directly to run detailed frame-by-frame detection analysis with downloadable annotated assets.
*   **Compliance History Logs:** Query violation histories, filter records by time/type, and export full reports as CSV sheets.

---

## 📁 Repository Structure

```text
SafeGuard/
├── backend/
│   ├── alerts/           # Alert manager (Email & WhatsApp notify services)
│   ├── api/              # API router endpoints (/health, /upload, /violations, /stats)
│   ├── db/               # SQLAlchemy engine setup and SQLite database models
│   ├── detection/        # YOLOv8s ONNX model processing and CV2 frame annotator
│   ├── websocket/        # WebSocket live stream frame controller
│   ├── .env.example      # Example environment config (copy to .env)
│   ├── best.onnx         # Pre-trained YOLOv8s ONNX model (42.7 MB)
│   ├── main.py           # FastAPI server entry point
│   ├── requirements.txt  # Python package dependencies
│   └── test_backend.py   # Integration verification script
│
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios backend API client
│   │   ├── components/   # Shared UI parts (Sidebar, Navbar, Cards)
│   │   ├── pages/        # Dashboard, Violations, Upload, Settings views
│   │   ├── App.jsx       # App shell & router configurations
│   │   └── index.css     # TailwindCSS v4 typography and color styles
│   ├── index.html        # SPA entrypoint
│   ├── package.json      # React dependencies
│   └── vite.config.js    # Vite dev server with proxy settings
│
└── .gitignore            # Git exclusion config (ignores database, node_modules, temp, etc.)
```

---

## 🛠️ Installation & Setup

### Prerequisites

*   **Python:** Version `3.8` to `3.11` recommended.
*   **Node.js:** Version `18.x` or newer (with `npm`).
*   **ONNX model:** The pre-trained YOLOv8s model is located at `backend/best.onnx`.

---

### 1. Backend Setup (FastAPI)

1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```

2.  Create and activate a Python virtual environment:
    ```bash
    python -m venv venv
    
    # On Windows:
    venv\Scripts\activate
    
    # On Linux/macOS:
    source venv/bin/activate
    ```

3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure the environment variables:
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Open `.env` and fill out your configurations (e.g. set `ENABLE_EMAIL_ALERTS` or `ENABLE_WHATSAPP_ALERTS` to `true` and add your SMTP / Twilio API keys).

5.  Run the backend test script to verify dependencies and model loading:
    ```bash
    python test_backend.py
    ```

6.  Start the FastAPI server:
    ```bash
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The server API will be live at `http://localhost:8000`. You can access the interactive Swagger documentation at `http://localhost:8000/docs`.

---

### 2. Frontend Setup (React)

1.  Navigate to the frontend directory:
    ```bash
    cd ../frontend
    ```

2.  Install the dependencies:
    ```bash
    npm install
    ```

3.  Start the React development server:
    ```bash
    npm run dev
    ```
    Open your browser and navigate to `http://localhost:5173`. The Vite proxy will automatically forward API requests to the backend server running on port 8000.

---

## ⚙️ Alert Settings

*   **Email Notifications:** Set up an App Password in your Google Account and enter it in `SMTP_PASSWORD` with `SMTP_USER` matching your sender email address.
*   **WhatsApp Notifications:** Configure Twilio WhatsApp Sandbox, enter your Twilio `ACCOUNT_SID`, `AUTH_TOKEN`, and verify your recipient number.
