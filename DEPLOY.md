# SIH26083: Free Cloud Deployment Guide

This guide provides step-by-step instructions to deploy the complete **Extreme Heatwave Early Warning & Human Thermal Stress System** on 100% free cloud infrastructure for the Smart India Hackathon live demonstration.

---

## 🏗️ Architecture on Free Cloud Tiers

```
[ Browser / Jury Phone ]
         │
         ▼
┌──────────────────────────────┐
│   Vercel / Render Static     │  --> Serves Leaflet.js Frontend
│   (https://sih-heatwave.app) │      High-contrast dark choropleth & Chart.js
└──────────────┬───────────────┘
               │ REST API Calls (CORS Enabled)
               ▼
┌──────────────────────────────┐
│    Render.com Web Service    │  --> FastAPI REST Microservices
│  (https://heatwave-api.onrender.com)
│                              │
│   ├── Auto-seeding on boot   │  --> Seeds 48 Ahmedabad wards, HVI & forecasts
│   └── SQLite Engine          │  --> data/processed/heatwave_sih.db
└──────────────────────────────┘
```

---

## Part 1: Backend Deployment (Render.com)

Render provides a generous free tier for Python web services with automated SSL, environment variable injection, and custom build steps.

### Step 1: Push Repository to GitHub
Ensure your repository is pushed to GitHub (public or private):
```bash
git add .
git commit -m "feat: complete Day 10 production hardening & deployment prep"
git push origin main
```

### Step 2: Create Web Service on Render
1. Log in to [Render.com](https://dashboard.render.com).
2. Click **New +** $\to$ **Web Service**.
3. Connect your GitHub repository: `SIH-PROJECT`.
4. Configure the service settings:
   - **Name**: `sih-heatwave-api`
   - **Region**: Singapore (Southeast Asia - lowest latency for Indian evaluators)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python -m backend.db.seed
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`

### Step 3: Configure Environment Variables
Under the **Environment** tab on Render, configure the following variables:

| Variable | Recommended Value | Required? | Purpose |
| :--- | :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Required | Enforces modern Python runtime |
| `DEFAULT_CITY` | `Ahmedabad` | Default | Target pilot city |
| `DEFAULT_LAT` | `23.03` | Default | Pilot city latitude |
| `DEFAULT_LON` | `72.58` | Default | Pilot city longitude |
| `USE_SYNTHETIC_DATA`| `false` | Default | Uses real Census 2011 & AMC GeoJSON |
| `TWILIO_ACCOUNT_SID`| *(Leave empty or add SID)* | Optional | Falls back to Twilio Sandbox Simulator |
| `TWILIO_AUTH_TOKEN` | *(Leave empty or add Token)* | Optional | Falls back to Twilio Sandbox Simulator |
| `TWILIO_PHONE_NUMBER`| *(Leave empty)* | Optional | Defaults to Twilio test sender |
| `GUPSHUP_API_KEY`   | *(Leave empty)* | Optional | Falls back to mock SMS gateway |
| `CDS_API_KEY`       | *(Leave empty)* | Optional | Historical backtesting uses cached ERA5 |

> [!NOTE]
> All third-party communication APIs (Twilio, Gupshup, CDS) feature **100% automated sandbox simulation fallbacks**. Even if zero external API keys are configured, every single endpoint and SMS trigger executes successfully without throwing exceptions!

### Step 4: Deploy & Verify
1. Click **Deploy Web Service**.
2. Wait 2–3 minutes for build and seeding completion.
3. Open your Render service URL in a browser:
   - Health check: `https://sih-heatwave-api.onrender.com/health`
   - Swagger Docs: `https://sih-heatwave-api.onrender.com/docs`
   - Ward GeoJSON: `https://sih-heatwave-api.onrender.com/api/wards/geojson`
4. Confirm response:
   ```json
   {
     "status": "ok",
     "database": "connected",
     "wards_count": 48
   }
   ```

---

## Part 2: Frontend Deployment (Vercel)

Vercel provides blazing-fast edge static hosting with zero cold start delays.

### Step 1: Deploy to Vercel
1. Log in to [Vercel.com](https://vercel.com).
2. Click **Add New...** $\to$ **Project**.
3. Import your GitHub repository.
4. Set **Root Directory** to `frontend`.
5. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL` = `https://sih-heatwave-api.onrender.com` (your Render backend URL)
6. Click **Deploy**.

### Alternative: Deploy Static Site on Render
If you prefer keeping frontend and backend under a single dashboard:
1. On Render, click **New +** $\to$ **Static Site**.
2. Root Directory: `frontend`
3. Publish Directory: `.` (or `dist` if building with Vite `npm run build`)
4. Add Environment Variable:
   - `VITE_API_BASE_URL` = `https://sih-heatwave-api.onrender.com`

---

## Part 3: Zero Committed Secrets Audit

Before presenting to SIH judges or making your GitHub repository public:
1. Verify `.gitignore` exists at project root:
   ```bash
   git status --ignored
   ```
2. Confirm `.env` is ignored:
   ```bash
   git check-ignore .env
   # Output should be: .env
   ```
3. Confirm SQLite database files and caches are excluded:
   ```bash
   git check-ignore data/processed/heatwave_sih.db
   # Output should be: data/processed/heatwave_sih.db
   ```

---

## Part 4: Cloud Staging Verification Checklist

- [ ] Backend `/health` returns `{"status": "ok", "database": "connected", "wards_count": 48}`
- [ ] Backend `/docs` interactive Swagger documentation loads and executes `/api/risk/AMD_01`
- [ ] Frontend loads high-contrast dark choropleth map centered on Ahmedabad
- [ ] Layer mode switcher toggles between Composite Risk, Thermal Hazard, and Vulnerability (HVI)
- [ ] Clicking any ward opens inspector sidebar with Chart.js 5-day predictive trajectory
- [ ] "Backtest Mode (May 2010)" button loads 2010 historical heatwave disaster data
- [ ] "Dispatch Early Warning Alert" fires and receives confirmed Message SID
- [ ] Mobile responsive layout loads cleanly on smartphone browser for jury demonstration
