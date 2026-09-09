#!/usr/bin/env bash
# SIH26083 - Unix/Linux Demo Launcher
set -e

echo "==============================================================================="
echo "     SIH26083: EXTREME HEATWAVE EARLY WARNING & THERMAL STRESS PLATFORM"
echo "                          LIVE DEMONSTRATION LAUNCHER"
echo "==============================================================================="

# 1. Verify Python & Node
python3 --version || { echo "Python 3 is required."; exit 1; }
node --version || { echo "Node.js is required."; exit 1; }

# 2. Seed DB if missing
if [ ! -f "data/processed/heatwave_sih.db" ]; then
    echo "[1/4] Seeding SQLite database..."
    python3 -m backend.db.seed
fi

# 3. Start Backend
echo "[2/4] Starting FastAPI backend on http://127.0.0.1:8000 ..."
python3 -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 4. Start Frontend
echo "[3/4] Starting Leaflet frontend on http://127.0.0.1:5173 ..."
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM EXIT

sleep 3
echo "==============================================================================="
echo "  Live Dashboard : http://127.0.0.1:5173"
echo "  API Docs       : http://127.0.0.1:8000/docs"
echo "==============================================================================="

# Try opening default browser
if command -v xdg-open > /dev/null; then
    xdg-open http://127.0.0.1:5173
elif command -v open > /dev/null; then
    open http://127.0.0.1:5173
fi

wait
