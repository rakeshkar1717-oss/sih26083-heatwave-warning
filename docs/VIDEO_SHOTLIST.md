# SIH26083: 2-Minute Demo Video Shotlist & Narration Script
## Extreme Heatwave Early Warning & Human Thermal Stress Index
**Total Target Video Runtime**: Exactly 120 Seconds (2 Minutes)  
**Resolution**: 1080p (1920x1080) at 60fps  
**Audio**: Clear voiceover with soft ambient background track (ducked during speech)

---

### Segment 1: The Problem & Opening Hook (0:00 – 0:15)
* **On Screen**:
  - Split screen: News headline of Indian heatwave deaths on left; satellite thermal map of India on right.
  - Text overlay: *"SIH26083: Extreme Heatwave Early Warning & Human Thermal Stress Index"*.
* **Visual Action**:
  - Slow zoom into Ahmedabad, Gujarat on Google Earth / satellite basemap.
* **Spoken Narration (Voiceover)**:
  > *"Across Indian cities, municipal heat alerts are triggered purely by dry air temperature. But a 38-degree humid afternoon in Gujarat is far deadlier than 42 degrees in the desert because human sweat cannot evaporate. To save lives, we need hyper-local human thermal stress intelligence."*

---

### Segment 2: Live System Architecture & Leaflet Dashboard (0:15 – 0:30)
* **On Screen**:
  - Full-screen view of the Leaflet.js choropleth dashboard at `http://localhost:5173`.
  - Dark Matter CartoDB basemap with 48 Ahmedabad municipal wards color-coded by composite risk.
* **Visual Action**:
  - Cursor moves to header, highlighting the `🟢 Online (48 Wards)` status pill and pilot city badge.
  - Hovering cursor across central and southern wards, showing quick interactive hover effects.
* **Spoken Narration (Voiceover)**:
  > *"Meet our operational early warning platform. Operating on 48 administrative wards of Ahmedabad, our system ingests multi-source meteorological feeds and combines biometeorological hazard with socio-demographic vulnerability."*

---

### Segment 3: Tri-Index Biometeorology & Layer Switcher (0:30 – 0:45)
* **On Screen**:
  - Close-up of the map layer switcher buttons in top-left.
* **Visual Action**:
  - Click **"Thermal Hazard"** button $\to$ Map transitions to yellow and orange shades reflecting 0–100 biometeorological stress.
  - Click **"Vulnerability (HVI)"** button $\to$ Map shifts to demographic vulnerability distribution.
  - Click back to **"Composite Risk"** button $\to$ Fused 60/40 risk tier returns.
* **Spoken Narration (Voiceover)**:
  > *"We go beyond basic heat index. Our engine calculates the ISO 7243 Outdoor Wet Bulb Globe Temperature—accounting for direct solar radiation and wind cooling—alongside UTCI and NOAA Heat Index. Fusing this with Census demographic vulnerability reveals true street-level danger."*

---

### Segment 4: Ward Deep-Dive & Predictive 5-Day Forecast (0:45 – 1:00)
* **On Screen**:
  - Clicking on a high-risk ward: **Vatva (AMD_17)** in South Zone.
  - Right-hand Inspector Sidebar slides open smoothly.
* **Visual Action**:
  - Focus camera on the 6 metric tiles (Air Temp, Heat Index, WBGT, UTCI, Hazard Score, HVI).
  - Scroll down to show the demographic breakdown bars (61.4% slum density, 56.8% outdoor labor).
  - Highlight the Chart.js 5-day predictive risk forecast curve showing rising danger over the weekend.
* **Spoken Narration (Voiceover)**:
  > *"Clicking Vatva reveals severe conditions: while air temp is 38 degrees, WBGT exceeds 32 degrees—the international threshold where continuous manual labor must cease. Notice our 5-day predictive engine projecting rising heat risk days in advance."*

---

### Segment 5: Automated Early Warning SMS & WhatsApp Dispatch (1:00 – 1:15)
* **On Screen**:
  - Bottom of the sidebar drawer showing the glowing **"Dispatch Early Warning Alert"** button.
  - Mobile phone overlay appearing on the right side of the screen.
* **Visual Action**:
  - Click **"Dispatch Early Warning Alert"**.
  - Modal pops up: *"Early Warning Alert Dispatched! SID: SM94A... Status: Delivered"*.
  - Mobile phone screen lights up with an incoming SMS notification containing localized NDMA advisories, cooling shelter locations, and water tanker stations.
* **Spoken Narration (Voiceover)**:
  > *"With one click—or via automated threshold triggers—our gateway dispatches localized, vernacular SMS and WhatsApp advisories directly to labor contractors and community leaders, complete with work-rest schedules and hydration directives."*

---

### Segment 6: THE CLINCHER: Historical Backtest Validation (1:15 – 1:30)
* **On Screen**:
  - Top map overlay: Cursor clicks **"🕒 Backtest Mode (May 2010)"**.
* **Visual Action**:
  - Map instantly transforms into intense crimson and purple emergency choropleth.
  - Emergency banner at top flashes: *"HISTORICAL BACKTEST MODE: May 2010 Landmark Heatwave"*.
  - Pop open the Slide 7 publication graph showing the May 20–23 peak hazard curve matched against 1,344 excess deaths.
* **Spoken Narration (Voiceover)**:
  > *"Does it work in reality? We validated our engine against the catastrophic May 2010 Ahmedabad heatwave using Copernicus ERA5 reanalysis. Our model flagged a 94 out of 100 emergency 48 hours prior to the peak mortality spike documented by Azhar et al. in PLOS ONE."*

---

### Segment 7: Production Rigor & Full API Architecture (1:30 – 1:45)
* **On Screen**:
  - Fast montage:
    1. VS Code terminal running `pytest backend/tests/ -v` showing **58 Passed in 2.78s**.
    2. FastAPI Swagger UI at `http://localhost:8000/docs` executing `/api/wards/geojson`.
    3. Docker desktop running the containerized services.
* **Visual Action**:
  - Highlight the clean test pass rate and modular Python architecture.
* **Spoken Narration (Voiceover)**:
  > *"Engineered with FastAPI, PostGIS-ready SQLite, and Leaflet, the system is covered by 58 automated tests with a 100% pass rate. It runs entirely in Docker or local scripts with zero proprietary dependencies."*

---

### Segment 8: National Impact & Conclusion (1:45 – 2:00)
* **On Screen**:
  - Map of India showing icons popping up over Delhi, Nagpur, Hyderabad, and Ahmedabad.
  - Title card: *"SIH26083: Extreme Heatwave Early Warning Platform | Team ClimateResilience"*.
* **Visual Action**:
  - Fade to closing slide with team names, GitHub repository link, and live deployment URL.
* **Spoken Narration (Voiceover)**:
  > *"Designed for seamless expansion to all 100+ Indian Smart Cities, our platform empowers municipal corporations to transform heat action plans from passive documents into proactive life-saving interventions. Thank you."*
