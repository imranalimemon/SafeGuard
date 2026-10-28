@echo off
setlocal
cd /d "%~dp0" || exit /b 1

REM Both servers stay in this terminal. concurrently owns their process trees.
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js is missing. Follow README.md clean-machine setup.
    exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm is missing. Follow README.md clean-machine setup.
    exit /b 1
)
if not exist "node_modules\.bin\concurrently.cmd" (
    echo [ERROR] Root dependencies are missing. Run npm install in the repository root.
    exit /b 1
)
if not exist "frontend\node_modules\vite\bin\vite.js" (
    echo [ERROR] Frontend dependencies are missing. Run npm --prefix frontend ci.
    exit /b 1
)

set "SG_ORIGINAL_PATH=%PATH%"
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "backend\.venv\Scripts\activate.bat" (
    call "backend\.venv\Scripts\activate.bat"
) else if exist "backend\venv\Scripts\activate.bat" (
    call "backend\venv\Scripts\activate.bat"
)
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is missing. Create .venv and install backend requirements.
    exit /b 1
)
call python -B -c "import fastapi, uvicorn, cv2, onnxruntime, sqlalchemy, PIL, tzdata, cryptography, multipart, websockets; from pydantic import model_validator" >nul 2>nul
if errorlevel 1 (
    echo [WARNING] Preferred virtual environment cannot load the backend runtime. Trying the original PATH Python.
    set "PATH=%SG_ORIGINAL_PATH%"
    set "VIRTUAL_ENV="
    call python -B -c "import fastapi, uvicorn, cv2, onnxruntime, sqlalchemy, PIL, tzdata, cryptography, multipart, websockets; from pydantic import model_validator" >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Backend runtime dependencies are missing. Install backend/requirements.txt in a working Python environment.
        exit /b 1
    )
)

REM Delivery mode is process-only; saved DB toggles cannot override preview.
if not defined ALERT_DELIVERY_MODE set "ALERT_DELIVERY_MODE=preview"
if not defined ALLOWED_ORIGINS set "ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173"
set "VITE_BACKEND_URL=http://127.0.0.1:8000"
echo Starting backend http://127.0.0.1:8000 and frontend http://127.0.0.1:5173
echo Alert delivery mode: %ALERT_DELIVERY_MODE%
echo Press Ctrl+C to stop both. Read startup errors below; startup is not a health check.

call "node_modules\.bin\concurrently.cmd" --kill-others --success all --names BACKEND,FRONTEND --prefix-colors cyan,magenta "cd backend && python -B -m uvicorn main:app --host 127.0.0.1 --port 8000" "npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort"
set "SG_EXIT=%ERRORLEVEL%"
endlocal & exit /b %SG_EXIT%
