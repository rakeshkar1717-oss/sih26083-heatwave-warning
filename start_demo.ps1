# SIH26083 - PowerShell Demo Launcher
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "     SIH26083: EXTREME HEATWAVE EARLY WARNING & THERMAL STRESS PLATFORM" -ForegroundColor Yellow
Write-Host "                          LIVE DEMONSTRATION LAUNCHER" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan

$env:PATH = "C:\Program Files\nodejs;" + $env:PATH

# 1. Check Python
$pythonVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python is not found on PATH."
    exit 1
}
Write-Host "[1/5] Python runtime: $pythonVer" -ForegroundColor Green

# 2. Check Database
if (-not (Test-Path "data/processed/heatwave_sih.db")) {
    Write-Host "[2/5] Database not found. Seeding database..." -ForegroundColor Yellow
    python -m backend.db.seed
} else {
    Write-Host "[2/5] SQLite database verified (data/processed/heatwave_sih.db)." -ForegroundColor Green
}

# 3. Start Backend
Write-Host "[3/5] Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$backendProc = Start-Process python -ArgumentList "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000" -PassThru -WindowStyle Minimized

# 4. Start Frontend
Write-Host "[4/5] Starting Leaflet Dashboard on http://127.0.0.1:5173 ..." -ForegroundColor Cyan
$frontendProc = Start-Process npm -ArgumentList "--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173" -PassThru -WindowStyle Minimized

# 5. Wait and Open Browser
Write-Host "[5/5] Waiting for server readiness..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "`n===============================================================================" -ForegroundColor Green
Write-Host "               DEMO SYSTEM IS LIVE AND OPERATIONAL!" -ForegroundColor White
Write-Host "  * Web Dashboard : http://127.0.0.1:5173" -ForegroundColor Yellow
Write-Host "  * REST API Docs : http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "  * Health Check  : http://127.0.0.1:8000/health" -ForegroundColor Yellow
Write-Host "===============================================================================`n" -ForegroundColor Green

Start-Process "http://127.0.0.1:5173"

Write-Host "Servers running in background. Press Ctrl+C or close this window when finished." -ForegroundColor Gray
try {
    while ($true) { Start-Sleep -Seconds 2 }
} finally {
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "All demo processes stopped." -ForegroundColor Red
}
