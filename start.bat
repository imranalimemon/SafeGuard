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
call python -B -m uvicorn --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] The selected Python has no Uvicorn. Install backend/requirements.txt in its environment.
    exit /b 1
)

REM The process environment takes precedence over backend/.env and saved DB toggles.
if not defined ALERT_DELIVERY_MODE set "ALERT_DELIVERY_MODE=preview"
set "VITE_BACKEND_URL=http://127.0.0.1:8000"
echo Starting backend http://127.0.0.1:8000 and frontend http://127.0.0.1:5173
echo Alert delivery mode: %ALERT_DELIVERY_MODE%
echo Press Ctrl+C to stop both. Read startup errors below; startup is not a health check.

call "node_modules\.bin\concurrently.cmd" --kill-others --success all --names BACKEND,FRONTEND --prefix-colors cyan,magenta "cd backend && python -B -m uvicorn main:app --host 127.0.0.1 --port 8000" "npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort"
set "SG_EXIT=%ERRORLEVEL%"
endlocal & exit /b %SG_EXIT%
