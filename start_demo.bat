@echo off
title SIH26083 - Live Demo Launcher
echo ===============================================================================
echo      SIH26083: EXTREME HEATWAVE EARLY WARNING & THERMAL STRESS PLATFORM
echo                           LIVE DEMONSTRATION LAUNCHER
echo ===============================================================================
echo.

:: Ensure Node.js is on PATH
set "PATH=C:\Program Files\nodejs;%PATH%"

:: 1. Verify Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    pause
    exit /b 1
)
echo [1/5] Python runtime verified.

:: 2. Check and seed database if missing
if not exist "data\processed\heatwave_sih.db" (
    echo [2/5] Database not found. Seeding 48 Ahmedabad wards and forecasts...
    python -m backend.db.seed
) else (
    echo [2/5] SQLite database verified (data\processed\heatwave_sih.db).
)

:: 3. Start FastAPI Backend
echo [3/5] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "SIH26083 Backend" /min cmd /c "python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000"

:: 4. Start Vite Frontend Server
echo [4/5] Starting Leaflet Dashboard on http://127.0.0.1:5173 ...
start "SIH26083 Frontend" /min cmd /c "npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173"

:: 5. Wait for server readiness and launch browser
echo [5/5] Waiting for server initialization...
timeout /t 3 /nobreak >nul

echo.
echo ===============================================================================
echo                DEMO SYSTEM IS LIVE AND RUNNING INDEFINITELY!
echo   * Web Dashboard : http://127.0.0.1:5173
echo   * REST API Docs : http://127.0.0.1:8000/docs
echo   * Health Probe  : http://127.0.0.1:8000/health
echo ===============================================================================
echo.
echo Launching your default browser now...
start http://127.0.0.1:5173

echo Press any key to stop background servers when your demo is finished...
pause >nul

echo Terminating servers...
taskkill /fi "WINDOWTITLE eq SIH26083 Backend*" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq SIH26083 Frontend*" /t /f >nul 2>&1
echo System shut down cleanly.
