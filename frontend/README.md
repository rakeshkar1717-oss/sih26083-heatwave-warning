# SIH26083: Interactive Leaflet Heatwave Choropleth Dashboard

Interactive web dashboard for **SIH26083: Extreme Heatwave Early Warning & Human Thermal Stress Index**.
Visualizes municipal ward boundaries, high-resolution biometeorological thermal indices (NOAA Heat Index, Outdoor WBGT, UTCI), socio-demographic vulnerability (HVI), 5-day predictive risk forecasts, and automated early warning alert dispatches.

---

## Prerequisites

1. **Backend Running**:
   The FastAPI backend must be running on `http://127.0.0.1:8000`:
   ```bash
   uvicorn backend.api.main:app --reload --port 8000
   ```
2. **Node.js (Optional but recommended)**:
   Node.js v18+ and npm installed.

---

## Quick Start (Two Methods)

### Method A: Modern Vite Dev Server (Recommended)
From the `/frontend` directory:
```bash
cd frontend
npm install
npm run dev
```
- Open your browser at: **`http://localhost:5173`**

### Method B: Zero-Dependency Python Static Server
If testing in an environment without Node/npm:
```bash
cd frontend
python -m http.server 3000
```
- Open your browser at: **`http://localhost:3000`**

---

## Features & Controls

1. **Interactive Choropleth Layer**:
   - Color-coded municipal ward polygons for Ahmedabad (48 wards) across 5 risk tiers:
     - `Low (<0.25)`: Green
     - `Moderate (0.25 - 0.50)`: Yellow
     - `High (0.50 - 0.70)`: Orange
     - `Very High (0.70 - 0.85)`: Red
     - `Extreme (≥ 0.85)`: Purple
2. **Layer Mode Toggles**:
   - **Composite Risk**: Synthesized hazard $\times$ vulnerability score.
   - **Thermal Hazard**: 0–100 biometeorological stress score.
   - **Vulnerability (HVI)**: Census/PLFS demographic sensitivity index.
3. **Interactive Ward Inspection**:
   - Click any ward to open the sidebar with temperature, WBGT, Heat Index, UTCI, demographic factors, and actionable civic advisories.
   - Popup includes an embedded **Chart.js 5-day predictive risk forecast mini-chart**.
4. **City Alert Emergency Banner**:
   - Automatically flashes an emergency warning across the top of the screen if any ward breaches the Extreme threshold.
5. **One-Click Early Warning Dispatch**:
   - Click "Dispatch Early Warning Alert" to test SMS/WhatsApp notification delivery via Twilio/Gupshup gateway.
6. **Live Auto-Refresh**:
   - Polls `/health` and re-fetches live telemetry every 60 seconds without page reloads.

---

## Configuration

To point the dashboard to a remote or staging backend, configure `VITE_API_BASE_URL` in a `.env` file inside `/frontend`:
```env
VITE_API_BASE_URL=http://your-backend-server:8000
```
Or edit `frontend/config.js` directly.
