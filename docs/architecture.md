# SIH26083: Extreme Heatwave Early Warning & Human Thermal Stress Index
## Master System Architecture & Technical Specification (Days 1–9 Complete)

> **Document Purpose**: Drop-in reference for Smart India Hackathon Technical Presentation Slide 4 (System Architecture) and comprehensive evaluation guide for jury members.

---

### 1. High-Level Full System Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                  METEOROLOGICAL OBSERVATION & REANALYSIS                          |
|                                                                                                   |
|     [Open-Meteo API]                    [NASA POWER API]                     [Copernicus ERA5]    |
|   Live Forecast & Observations        Solar Radiation & Agrometeorology       Atmospheric Reanalysis|
|       (Hourly Grid)                       (Hourly Satellite)                  (NetCDF / Archive)  |
+-------------------+------------------------------+------------------------------------+-----------+
                    |                              |                                    |
                    +------------------------------+------------------------------------+
                                                   |
                                                   v
+---------------------------------------------------------------------------------------------------+
| 1. DATA INGESTION & VALIDATION ROUTER (/backend/data_ingestion)                                    |
|   - Unified router: get_weather_data() & pull_historical_weather()                                |
|   - Strict schema enforcement via backend.models.validate_weather_dataframe()                     |
|   - Fixed Canonical Schema: [timestamp, lat, lon, temp_c, humidity_pct, wind_speed_ms,            |
|                              solar_radiation_wm2, source]                                         |
+--------------------------------------------------+------------------------------------------------+
                                                   |
                                                   v
+---------------------------------------------------------------------------------------------------+
| 2. BIOMETEOROLOGICAL THERMAL INDEX ENGINE (/backend/index_calculation)                            |
|   - NOAA / OSHA Heat Index (°C) [Rothfusz Multi-Polynomial Regression]                            |
|   - Outdoor WBGT (°C) [ISO 7243 Convective Wind & Solar Radiative Model]                          |
|   - UTCI Bioclimate Index (°C) [COST Action 730 / Bröde 6th-Order Polynomial]                    |
|   - Normalized Thermal Stress Hazard Score (0–100): 40% WBGT + 35% HI + 25% UTCI                  |
+-----------------------+---------------------------------------------------------------------------+
                        |
                        +---------------------------------------+
                        |                                       |
                        v                                       v
+------------------------------------+  +-----------------------------------------------------------+
| 3. GIS WARD BOUNDARIES & SPATIAL   |  | 4. DEMOGRAPHIC HEAT VULNERABILITY MODEL (HVI)             |
|    JOIN (/backend/gis)             |  |    (/backend/vulnerability_model)                         |
|   - boundary_loader.py (WGS84)     |  |   - Census 2011 & PLFS Socio-Economic Microdata          |
|   - spatial_join.py (sjoin within) |  |   - 5 Vectors: Elderly (25%), Outdoor Labor (25%),        |
|   - sjoin_nearest centroid fallback|  |     Slum Density (20%), Green Cover (15%), Beds (15%)    |
+-----------------------+------------+  +-----------------------+-----------------------------------+
                        |                                       |
                        +-------------------+-------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------------------+
| 5. COMPOSITE WARD RISK SYNTHESIS ENGINE                                                           |
|   - Formula: Final Composite Risk = 0.60 × Thermal Hazard + 0.40 × Demographic Vulnerability (HVI)|
|   - 5 Categorical Risk Tiers: LOW (<0.25) | MODERATE (0.25-0.50) | HIGH (0.50-0.70) |              |
|                               VERY HIGH (0.70-0.85) | EXTREME (>0.85)                             |
+-------------------------------------------+-------------------------------------------------------+
                                            |
                                            +---------------------------------------+
                                            |                                       |
                                            v                                       v
+-------------------------------------------------------+   +---------------------------------------+
| 6. DATABASE PERSISTENCE LAYER (/backend/db)           |   | 7. MULTI-DAY PREDICTIVE FORECASTING   |
|   - SQLAlchemy 2.0 ORM Engine                         |   |    (/backend/forecasting)             |
|   - Local Zero-Dependency SQLite / PostgreSQL         |   |   - 1 to 5 Day Hourly Projections     |
|   - Tables: WardBoundary, WardVulnerability,          |   |   - Diurnal Peak Hazard Extraction    |
|             WeatherReading, RiskForecast, AlertLog    |   |   - City-wide Coordinate Caching      |
+---------------------------+---------------------------+   +-------------------+-------------------+
                            |                                                   |
                            +-------------------+-------------------------------+
                                                |
                                                v
+---------------------------------------------------------------------------------------------------+
| 8. FASTAPI REST MICROSERVICES LAYER (/backend/api)                                                |
|   - GET /health                : Real-time DB and service heartbeat probe                         |
|   - GET /api/wards/geojson     : RFC 7946 GeoJSON choropleth with joined biometeorological fields  |
|   - GET /api/risk/{ward_id}    : Ward composite hazard, HVI, advisory, and 5-day forecasts        |
|   - GET /api/weather/{ward_id} : Meteorological history and latest thermal indices                |
|   - GET /api/forecast/{ward_id}: 5-day predictive risk timeline                                   |
|   - POST /api/alert/trigger    : Automated SMS/WhatsApp early warning dispatch                    |
|   - GET /api/backtest/*        : Historical backtesting validation summaries & GeoJSON           |
+-----------------------------------------------+---------------------------------------------------+
                                                |
                        +-----------------------+-----------------------+
                        |                                               |
                        v                                               v
+-----------------------------------------------+   +-----------------------------------------------+
| 9. LEAFLET CHOROPLETH DASHBOARD (/frontend)   |   | 10. HISTORICAL BACKTESTING VALIDATION         |
|   - CartoDB Dark Matter Responsive GIS Map    |   |     (/backend/backtesting)                    |
|   - Layer Switcher: Risk / Hazard / HVI       |   |   - Benchmark: Ahmedabad May 2010 Heatwave    |
|   - Ward Inspector Drawer & Weather Gauges    |   |   - Empirical Mortality: +1,344 excess deaths |
|   - Interactive Chart.js 5-Day Forecast Curves|   |     (Azhar et al. 2014, PLOS ONE)             |
|   - One-Click "Backtest Mode (May 2010)"      |   |   - Proactive 48-hour Code Red Early Warning  |
|   - System Status Online Pill & Loading States|   |   - Matplotlib Slide 7 Publication Chart      |
|   - Educational Plain-English Explainer Modal |   |                                               |
+-----------------------------------------------+   +-----------------------------------------------+
```

---

### 2. Core Mathematical Formulations

#### A. NOAA/OSHA Apparent Temperature (Heat Index)
Derived using the full 9-term multivariate Rothfusz regression equation:
$$\text{HI}_F = c_1 + c_2 T + c_3 R + c_4 T R + c_5 T^2 + c_6 R^2 + c_7 T^2 R + c_8 T R^2 + c_9 T^2 R^2$$
*Where $T$ is dry-bulb temperature in Fahrenheit, and $R$ is relative humidity in percent.*  
*Low humidity (<13% RH) and high humidity (>85% RH) adjustments are applied conditionally per NWS criteria.*

#### B. Outdoor Wet Bulb Globe Temperature (ISO 7243)
Outdoor physical work-rest ratio standard accounting for vapor pressure ($e$ in hPa), convective dissipation from 10m wind speed ($v$ in m/s), and direct downward solar irradiance ($S$ in $\text{W/m}^2$):
$$\text{WBGT}_{\text{outdoor}} = 0.567 \cdot T_a + 0.393 \cdot e + 3.94 + \left(\frac{S}{100.0}\right) \cdot \frac{0.75}{(v + 0.5)^{0.25}}$$

#### C. Universal Thermal Climate Index (Bröde UTCI)
Operational polynomial approximation evaluating physiological energy balance and mean radiant temperature offset ($T_{mrt} - T_a$):
$$\text{UTCI} = T_a + \text{offset}(T_a, v_{10m}, e, T_{mrt} - T_a)$$

#### D. Composite Thermal Stress Score (0–100 Hazard)
Weighted biometeorological synthesis normalized against physiological failure thresholds:
$$\text{Thermal Hazard} = 0.40 \cdot \text{Norm}(\text{WBGT}) + 0.35 \cdot \text{Norm}(\text{HI}) + 0.25 \cdot \text{Norm}(\text{UTCI})$$

#### E. Heat Vulnerability Index (HVI)
Multi-factor demographic susceptibility score derived from municipal Census and PLFS indicators:
$$\text{HVI} = 0.25 \cdot \text{elderly} + 0.25 \cdot \text{outdoor\_workers} + 0.20 \cdot \text{slums} + 0.15 \cdot \left(\frac{1}{\text{green} + \epsilon}\right) + 0.15 \cdot \left(\frac{1}{\text{hospital\_beds} + \epsilon}\right)$$

#### F. Final Composite Ward Risk Score
$$\text{Final Risk} = 0.60 \cdot \text{Thermal Hazard Score} + 0.40 \cdot \text{HVI}$$

---

### 3. REST API Contract Overview

| Endpoint | Method | Response Schema | Description |
| :--- | :---: | :--- | :--- |
| `/health` | `GET` | `{"status": "ok", "database": "connected", "wards_count": 48}` | Service & persistence heartbeat probe |
| `/api/wards/geojson` | `GET` | GeoJSON `FeatureCollection` (RFC 7946) | 48 Wards with joined real-time biometeorology & risk |
| `/api/risk/{ward_id}` | `GET` | `WardRiskScore` Pydantic Model | Hazard, HVI, advisory, and 5-day risk forecast |
| `/api/weather/{ward_id}` | `GET` | Meteorological history dictionary | Current weather observations + 24h history |
| `/api/forecast/{ward_id}` | `GET` | 5-day predictive trajectory | Daily predicted risk scores and risk tiers |
| `/api/alert/trigger` | `POST` | `AlertResponse` Model | Triggers Twilio/Gupshup SMS/WhatsApp dispatch |
| `/api/population-impact/{ward_id}` | `GET` | `PopulationImpactResponse` | Absolute cohort headcounts & clinical health actions |
| `/api/copilot/chat` | `POST` | `CopilotChatResponse` | Conversational personal thermal risk & dashboard guidance |
| `/api/backtest/summary` | `GET` | Historical event metadata | Benchmark citations and peak disaster statistics |
| `/api/backtest/timeline` | `GET` | 13-day historical trajectory | Daily historical heatwave progression (May 2010) |
| `/api/backtest/geojson` | `GET` | GeoJSON `FeatureCollection` | Peak historical disaster conditions (May 21, 2010) |

---

### 3.1 Heat Copilot Conversational Assistant Architecture (`/backend/copilot`)

```
+---------------------------------------------------------------------------------------------------+
| USER QUERY ("Is it safe to walk to college at 2 PM in Navrangpura?")                              |
+--------------------------------------------------+------------------------------------------------+
                                                   |
                                                   v
+---------------------------------------------------------------------------------------------------+
| 1. INTENT ROUTER (intent_router.py)                                                               |
|   - Regex & semantic keyword classification: personal_risk_query / general_question / dashboard_help|
|   - Optional LLM classification enhancement with automatic zero-downtime deterministic fallback   |
+--------------------------------------------------+------------------------------------------------+
                                                   |
         +-----------------------------------------+-----------------------------------------+
         | (personal_risk_query)                   | (general_question)                      | (dashboard_help)
         v                                         v                                         v
+------------------------------------+    +------------------------------------+    +------------------------------------+
| PERSONAL RISK HANDLER              |    | GENERAL Q&A HANDLER                |    | DASHBOARD HELP HANDLER             |
| (personal_risk_handler.py)         |    | (general_qa_handler.py)            |    | (dashboard_help_handler.py)        |
| - Entity extraction: time, activity|    | - Science FAQ: WBGT, UTCI,         |    | - Interactive guide for map layers,|
|   duration, and vulnerability      |    |   NOAA Heat Index, HVI formula     |    |   ward selection, 5-day charts,    |
| - Dynamic thermal strain modeling  |    | - Data sources: Census 2011, PLFS  |    |   backtest toggle & SMS alerts     |
| - ThermoGuard structured advice    |    | - 85.43% multi-horizon accuracy    |    +-----------------+------------------+
+-----------------+------------------+    +-----------------+------------------+                      |
                  |                                         |                                         |
                  +-----------------------------------------+-----------------------------------------+
                                                            |
                                                            v
+---------------------------------------------------------------------------------------------------+
| 2. OPTIONAL LLM POLISH & DETERMINISTIC FALLBACK (llm_client.py)                                   |
|   - Rephrases conversational output if ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY present|
|   - Strict invariant rule: NEVER invents or alters any calculated temperature, WBGT, or risk numbers|
+---------------------------------------------------------------------------------------------------+
```

---

### 4. Scientific Validation & Empirical Benchmarks

- **Benchmarked Disaster**: Ahmedabad May 15–27, 2010 Severe Heatwave (catalyst for South Asia's first Heat Action Plan).
- **Ground Truth Publication**: *Azhar GS, et al. (2014) "Heat-Related Mortality in India: Excess All-Cause Mortality Associated with the 2010 Ahmedabad Heat Wave". PLOS ONE 9(3): e91773.*
- **Model Finding**: The tri-index hazard crossed into **DANGER / CODE RED** ($HI > 52^\circ\text{C}$, $WBGT > 40^\circ\text{C}$, Hazard $82–94/100$) on May 20, 2010, **48 hours prior** to the peak mortality spike (310 deaths on May 21 vs. 100 baseline; total 1,344 excess deaths).
- **Slide 7 Visual**: Publication-quality 300 DPI chart generated at `docs/assets/historical_validation_may2010.png`.

---

### 5. Deployment & Quick Start Commands

#### Option A: One-Click Native Execution (Windows)
```cmd
start_demo.bat
```
*(Automatically seeds SQLite DB, launches FastAPI on :8000 and Vite on :5173, and opens browser).*

#### Option B: PowerShell Execution
```powershell
./start_demo.ps1
```

#### Option C: Unix/Linux Execution
```bash
chmod +x start_demo.sh && ./start_demo.sh
```

#### Option D: Production Multi-Container Docker
```bash
docker-compose up --build
```
*(FastAPI backend on port 8000, Nginx frontend on port 5173).*
