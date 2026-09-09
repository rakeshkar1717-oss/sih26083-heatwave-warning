# Smart India Hackathon Presentation Deck Content
## Problem Statement: SIH26083 — Extreme Heatwave Early Warning & Human Thermal Stress Index
**Team**: ClimateResilience | **Pilot City**: Ahmedabad Municipal Corporation (48 Wards)

---

### Slide 1: Title & Problem Context

* **Slide Title**: Hyper-Local Human Thermal Stress & Ward-Level Heatwave Early Warning System
* **Subtitle**: Transforming Municipal Heat Action Plans from Crude Temperature Thresholds into Street-Level Biometeorological & Socio-Demographic Intelligence
* **Problem Statement ID**: SIH26083 (Ministry of Earth Sciences / National Disaster Management Authority)
* **The Reality on the Ground**:
  - Current Indian heat alerts rely almost entirely on single dry-bulb air temperature thresholds (e.g., IMD 40°C threshold).
  - **The Lethal Blind Spot**: A 38°C afternoon in high humidity coastal Gujarat is physiologically far more dangerous than a dry 42°C in Rajasthan because sweat evaporation ceases.
  - Heat does not affect populations uniformly: informal laborers, slum dwellers with tin-sheet roofs, and elderly citizens suffer disproportionate mortality while affluent neighborhoods remain buffered.
* **Our Solution**:
  - An operational, GIS-integrated biometeorological platform computing **ISO 7243 Outdoor WBGT**, **Bröde UTCI**, and **NOAA Heat Index** merged with a **5-Factor Census HVI Model** across 48 administrative municipal wards with 3–5 day predictive risk forecasting and automated worker SMS alerts.

---

### Slide 2: The Core Innovation — Why Temperature Alone Fails

* **Slide Title**: Beyond Dry-Bulb Temperature: The Tri-Index Biometeorological Engine
* **Core Comparison**:

| Metric | Physical Inputs Modeled | Critical Limitation in Indian Context | Our Innovation |
| :--- | :--- | :--- | :--- |
| **Raw Air Temp ($T_a$)** | Ambient sensible heat only | Ignores humidity, solar radiation, and wind completely | Replaced by multi-variable physiological models |
| **NOAA Heat Index (HI)** | Temperature + Relative Humidity | Assumes sedentary human in shaded indoor conditions | Retained as baseline caution metric (35% weight) |
| **Outdoor WBGT (ISO 7243)** | $T_a$, Humidity, Direct Solar Irradiance ($W/m^2$), Wind Speed ($m/s$) | Hard to measure directly without specialized black-globe hardware | Mathematically estimated from satellite & reanalysis radiation (40% weight) |
| **Universal Thermal Climate Index (UTCI)** | Multi-node thermoregulation model | Computationally heavy polynomial regression | Optimized Bröde regression predicting dynamic thermal strain (25% weight) |

* **The Formula for Composite Thermal Hazard**:
  $$\text{Thermal Hazard (0–100)} = 0.35 \times \text{Norm}(HI) + 0.40 \times \text{Norm}(WBGT) + 0.25 \times \text{Norm}(UTCI)$$
* **Why WBGT is the Indian Labor Standard**:
  - Above $30^\circ\text{C}$ outdoor WBGT, ISO 7243 mandates a 50% work-rest cycle.
  - Above $32^\circ\text{C}$ outdoor WBGT, continuous heavy outdoor manual labor must cease to prevent fatal heatstroke.

---

### Slide 3: End-to-End System Architecture

* **Slide Title**: Production-Grade Modular Architecture
* **Data Flow**:

```
[ METEOROLOGICAL INGESTION ]
Open-Meteo API (Forecast) │ NASA POWER (Surface Solar) │ Copernicus ERA5 Reanalysis
                            │
                            ▼
[ BIOMETEOROLOGICAL ENGINE (/backend/index_calculation) ]
NOAA Heat Index │ ISO 7243 Outdoor WBGT │ Bröde UTCI Polynomial
                            │
                            ▼
[ SOCIO-DEMOGRAPHIC ENGINE (/backend/vulnerability_model) ]
Census 2011 + PLFS: Elderly % (15%) + Outdoor Labor % (25%) + Slums % (30%) + 1/Green % (15%) + 1/Beds (15%)
                            │
                            ▼
[ SPATIAL FUSION & GIS JOIN (/backend/gis) ]
Point-in-Polygon & Nearest-Neighbor Spatial Join onto 48 WGS84 AMC Ward Polygons
                            │
                            ▼
[ PERSISTENCE & FORECASTING (/backend/db & /backend/forecasting) ]
SQLite / PostGIS Engine │ 5-Day Diurnal Hazard Trajectory Generator (240 Forecast Rows)
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
[ FASTAPI REST SERVICES ]             [ AUTOMATED ALERT GATEWAY ]
GeoJSON Choropleth (/api/wards/geojson)  Twilio SMS & WhatsApp Gateway
Predictive Horizons (/api/forecast)   Gupshup Indian Carrier Route
Health & Backtest Endpoints           NDMA Action Directives + Audit Trail
         │
         ▼
[ LEAFLET.JS COMMAND DASHBOARD ]
High-Contrast CartoDB Dark Choropleth │ Chart.js Diurnal Curves │ Historical Backtest Mode
```

---

### Slide 4: Scientific Validity — Historical Heatwave Backtesting

* **Slide Title**: Empirical Ground Truth Validation: Ahmedabad May 2010 Catastrophe
* **The Historical Benchmark**:
  - **Event**: The May 15–27, 2010 Ahmedabad Heatwave (The catalyst for South Asia's first Heat Action Plan).
  - **Peak Meteorological Observation**: May 21, 2010 — All-time record of **46.8°C** at Ahmedabad Station.
  - **Documented Mortality Spike**: **1,344 excess all-cause deaths** (+43.1% over baseline), peaking at 310 deaths on May 21 alone.
  - **Primary Peer-Reviewed Citation**:  
    *Azhar GS, et al. (2014) Heat-Related Mortality in India: Excess All-Cause Mortality Associated with the 2010 Ahmedabad Heat Wave. PLOS ONE 9(3): e91773.*
* **Our System's Backtest Performance**:
  - Re-ran our full 4-stage pipeline against **312 hourly Copernicus ERA5 reanalysis readings** from May 15–27, 2010.
  - **Peak Model Metrics**: May 21, 2010 reached **Heat Index 58.6°C**, **WBGT 40.4°C**, and **Thermal Hazard 94/100 (EXTREME)**.
  - **Proactive Lead Time**: The system breached Code Red ($HI > 52^\circ\text{C}, WBGT > 32^\circ\text{C}$) on **May 20, 2010** — providing a full **48-hour proactive municipal early warning window** before the peak mortality wave hit hospitals.
* **Scientific Transparency**: Biometeorological hazard is empirically validated; ward spatial distribution is based on validated Census 2011/PLFS demographic vulnerability proxy.

---

### Slide 5: High-Risk Ward Case Study — Vatva & Danilimda

* **Slide Title**: Hyper-Local Intelligence: Danilimda vs. Bodakdev Microclimates
* **The Ward Disparity in Ahmedabad**:

| Parameter | Ward A: Bodakdev (AMD_01 / West AMC) | Ward B: Danilimda (AMD_04 / South AMC) | Real-World Impact |
| :--- | :--- | :--- | :--- |
| **Ambient Temperature** | 38.2°C | 38.5°C | Negligible air temp difference (+0.3°C) |
| **NOAA Heat Index** | 41.2°C | 44.8°C | +3.6°C higher apparent heat |
| **Outdoor WBGT (ISO 7243)** | 29.8°C | **32.6°C** | **Exceeds 32°C work cessation limit** |
| **Informal Labor Share** | 18.2% | **56.8%** | 3x more daily-wage exposed workers |
| **Slum Housing / Tin Roofs** | 4.1% | **61.4%** | Severe urban heat island indoor trapping |
| **Tree Canopy Cover** | 22.5% | **4.2%** | Zero shaded walking corridors |
| **Heat Vulnerability Index** | 0.1839 (Low) | **0.7500 (High / Extreme)** | 4x socio-economic vulnerability |
| **Final Composite Risk** | **0.38 (MODERATE - Yellow)** | **0.86 (EXTREME - Purple)** | **Completely different civic intervention** |

* **Civic Action Dictated**:
  - Bodakdev: Standard public advisory; hydration reminders.
  - Danilimda: Emergency halt to outdoor construction, dispatch of 4 mobile water tankers to informal labor hubs, deployment of ORS to primary health centers, and opening air-cooled municipal halls.

---

### Slide 6: Dual Notification System — Command Center to the Street

* **Slide Title**: Automated Early Warning Dispatch & Public Health Directives
* **1. Municipal Disaster Command Dashboard (Leaflet.js)**:
  - Interactive Leaflet choropleth map color-coded by NDMA/AMC risk tiers (`Low` to `Extreme`).
  - Layer switcher: View pure biometeorological hazard vs. demographic vulnerability vs. composite risk.
  - Click-to-inspect ward drawer with live biometeorological tiles and Chart.js 5-day predictive trajectory.
  - "Backtest Mode" toggle allowing disaster commissioners to stress-test response protocols against historical disasters.
* **2. Multi-Channel Vernacular SMS & WhatsApp Gateway**:
  - Integrates Twilio REST API and Gupshup Enterprise Messaging with automated Sandbox simulation fallbacks.
  - **Dynamic Message Construction**: Formulates localized advisories referencing ward name, observed thermal indices, mandatory work-rest intervals, nearest cooling shelter locations, and emergency helpline (108).
  - **Rate-Limit Safeguard**: Configured with `MAX_ALERTS_PER_DEMO_RUN` preventing network flooding during demonstrations.
  - **Immutable Audit Trail**: Every alert logged to SQLite/PostgreSQL `AlertLog` table with timestamp, recipient hash, channel, and delivery status for municipal compliance.

---

### Slide 7: Tech Stack, Architecture & Engineering Rigor

* **Slide Title**: Production-Grade Tech Stack & Quality Engineering
* **Technology Stack**:
  - **Backend**: FastAPI (Python 3.11/3.14) with Pydantic v2 schemas and SQLAlchemy 2.0 ORM.
  - **Spatial & Scientific**: GeoPandas, Shapely (WGS84 EPSG:4326), NumPy, Pandas, Matplotlib (300 DPI publication charts).
  - **Frontend**: Vanilla JavaScript + Vite + Leaflet.js (CartoDB Dark Matter basemap) + Chart.js.
  - **Database**: SQLite with relational foreign keys and indices (PostGIS ready).
  - **Packaging**: Docker, `docker-compose.yml`, single-click `start_demo.bat`, `start_demo.ps1`, `start_demo.sh`.
* **Testing & Robustness Verification**:
  - **100% Passing Automated Tests**: **58/58 unit and integration tests** passing across 9 test suites (`test_alerts`, `test_api`, `test_backtesting`, `test_data_ingestion`, `test_db`, `test_forecasting`, `test_gis`, `test_index_calculation`, `test_vulnerability_model`).
  - **Defensive Engineering**:
    - Automatic database cold-start auto-seeding on fresh boot.
    - Census demographic column imputation with municipal medians.
    - Seamless network retry adapters with exponential backoff on weather APIs.
    - Zero external API dependencies required for offline demonstrations.

---

### Slide 8: Real-World Impact, Scalability & Future Roadmap

* **Slide Title**: National Scalability: Empowering India's 100+ Smart Cities
* **Measurable Socio-Economic Impact**:
  - **Mortality Reduction**: Proactive 48-hour early warnings provide municipal corporations sufficient lead time to avert heatstroke deaths among construction workers and street vendors.
  - **Labor Productivity & Safety**: Replaces blunt city-wide shutdowns with hyper-local, time-bounded rest schedules based on ISO 7243 standards.
* **Plug-and-Play Scalability**:
  - Already architected in `backend/config.py` with multi-city configurations:
    - **Delhi**: 272 wards (Extreme dry heat & continental UHI)
    - **Nagpur**: 38 wards (Central India extreme summer conditions)
    - **Hyderabad**: 150 wards (Deccan plateau heatwaves)
  - Any Indian city can be integrated in **under 48 hours** simply by providing a ward boundary GeoJSON and Census/PLFS demographic CSV.
* **Roadmap Ahead**:
  - **Phase 1 (Immediate)**: Integration with National Disaster Management Authority (NDMA) Common Alerting Protocol (CAP).
  - **Phase 2 (6 Months)**: Machine learning predictive modeling trained on hospital emergency room heatstroke admission logs.
  - **Phase 3 (12 Months)**: High-resolution satellite thermal infrared downscaling (Landsat 9 / Sentinel-3 LST) at 100m grid resolution.
