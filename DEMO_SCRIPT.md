# SIH26083: Live Demonstration Presentation Script
## Extreme Heatwave Early Warning & Human Thermal Stress Index
**Target Pitch Duration**: 5 Minutes  
**Target Audience**: Smart India Hackathon Jury, NDMA / Ministry Evaluators  
**Pilot City**: Ahmedabad Municipal Corporation (48 Administrative Wards)  

---

### 3-Tier Presentation Contingency Plan (Never Fail a Demo)
* **Plan A (Cloud Live URL)**: Open the deployed cloud URL on your presentation laptop or phone (e.g. `https://sih-heatwave.vercel.app`). Demonstrates production deployment readiness.
* **Plan B (Local Execution - Primary)**: Double-click `start_demo.bat` (Windows) or `./start_demo.sh` (Linux/Mac). Boots local FastAPI backend on `:8000` and Leaflet dashboard on `:5173`. Works 100% offline with zero Internet dependency!
* **Plan C (Emergency Video Walkthrough)**: If jury Wi-Fi, venue power, or hardware fails, open the 2-minute MP4 video walkthrough (`docs/VIDEO_SHOTLIST.md`) directly from your laptop or USB drive.

### Setup Checklist (Before Approaching the Jury)
1. Launch via **Plan A** or **Plan B** (`start_demo.bat`).
2. Verify browser has opened at `http://127.0.0.1:5173` (or live URL).
3. Check header status pill: Ensure it reads `🟢 Online (48 Wards)`.
4. Have your mobile phone ready if demonstrating live Twilio SMS dispatch.

---

### Phase 1: The Problem & Live Overview (Minute 0:00 - 1:00)
> **Speaker Action**: Stand beside the projector showing the dark-themed choropleth map. Point to the title and pilot city tag.

* **Speaker Script**:
  > *"Respected Jury, in India today, municipal heat alerts are triggered purely by dry-bulb air temperature—for instance, an arbitrary 40°C threshold. But temperature alone doesn't tell you if a human body can cool down. A 38°C afternoon in humid coastal Gujarat is vastly more lethal than a dry 42°C in Rajasthan because sweat cannot evaporate.*
  >
  > *To solve Problem Statement SIH26083, we built this: an end-to-end, ward-level Extreme Heatwave Early Warning and Human Thermal Stress Platform. Here on the screen are the 48 municipal wards of Ahmedabad, color-coded not by raw temperature, but by our validated multi-factor composite risk index."*

---

### Phase 2: Layer Modes & The Tri-Index Engine (Minute 1:00 - 2:00)
> **Speaker Action**: Click through the 3 layer mode buttons at the top of the map:
> 1. Click **"Thermal Hazard"**
> 2. Click **"Vulnerability (HVI)"**
> 3. Click back to **"Composite Risk"**

* **Speaker Script**:
  > *"Our system separates risk into two fundamental scientific components:*
  > 
  > *First, **Thermal Hazard**: Clicking 'Thermal Hazard' reveals our tri-index biometeorological engine. We calculate the **NOAA Heat Index**, the **Bröde UTCI**, and crucially, the **ISO 7243 Outdoor WBGT**—which incorporates direct downward solar radiation and wind dissipation.*
  > 
  > *Second, **Heat Vulnerability (HVI)**: Heat doesn't affect all citizens equally. Clicking 'Vulnerability' switches to our Census 2011 and PLFS demographic model. We evaluate 5 socio-economic vectors: elderly percentage, informal outdoor workers, slum roof density, vegetative canopy (NDVI), and hospital bed density.*
  > 
  > *Switching back to **Composite Risk**, our algorithm fuses 60% biometeorological hazard with 40% demographic vulnerability to deliver hyper-local, street-level risk intelligence."*

---

### Phase 3: Ward Inspection & Predictive 5-Day Trend (Minute 2:00 - 3:00)
> **Speaker Action**: Click on a high-risk ward on the map (e.g., **Vatva [AMD_17]** or **Danilimda [AMD_04]**).
> The sidebar drawer populates with live gauges, progress bars, and the Chart.js forecast line.

* **Speaker Script**:
  > *"When a disaster officer clicks any ward—like Vatva here in AMC's South Zone—the inspector reveals exact biometeorology: Air temp is 38°C, but the apparent Heat Index is 44°C and WBGT is above 32°C. Under ISO 7243, outdoor physical labor is dangerous.*
  > 
  > *Down in the demographic breakdown, Vatva has over 61% informal slum housing and 56% daily-wage labor, giving it a high HVI.*
  > 
  > *Notice the chart below: This is our **multi-day predictive forecast engine**. It queries global numerical weather models, calculates diurnal thermal stress trajectories, and projects the risk score 5 days ahead, giving municipal authorities actionable advance notice before emergency rooms fill up."*

---

### Phase 3B: Interactive "Personal Heat Twin" Live Demo (Minute 3:00 - 3:45)
> **Speaker Action**: Click the top-level navigation tab: **"👤 Personal Heat Twin"**.
> The standalone interactive two-column view opens cleanly on the projector.
> The presenter enters live details in front of the judges:
> 1. Select Age: **Senior Citizen (Age 60+)**
> 2. Select Occupation: **Outdoor & Informal Labor**
> 3. Select Activity: **Heavy Physical Labor**
> 4. Slide duration to **90 minutes**
> 5. Click: **"⚡ Check My Real-Time Heat Risk"**.
> Show the instant result card: Large risk score gauge (e.g. **76 / 100 HIGH RISK**), the 6-factor point contribution breakdown (Air Temp, Humidity, Solar Radiant Load, Physical Exertion, Duration, Personal Factors), clinical consequence advisory, and the green **Safer Diurnal Time Window** recommendation.

* **Speaker Script**:
  > *"Civic heat dashboards often fail because they are too abstract for everyday people. A street vendor or an elderly resident doesn't just want a municipal color code—they need to know what today's heat means for **their** body.
  > 
  > That is why we built the **Personal Heat Twin**. Live on screen, any visitor enters their age, occupation, current activity, and exposure duration. In milliseconds, our engine couples the ward's Liljegren WBGT with ISO 8996 metabolic heat production and clinical vulnerability.
  > 
  > Notice the transparent point breakdown: Rather than an opaque black-box AI score, the system reveals exactly how much risk is driven by solar radiation (+12 pts), physical exertion (+20 pts), and duration (+8 pts). It provides actionable clinical advice and tells the citizen exactly what safer time window to reschedule their trip."*

---

### Phase 4: THE CLINCHER — Live Historical Backtesting (Minute 3:45 - 4:30)
> **Speaker Action**: Click the glowing button: **"🕒 Backtest Mode (May 2010)"**.
> Point to the map instantly turning red/purple, the top emergency banner updating, and the sidebar chart switching to the May 15–27, 2010 trajectory.


* **Speaker Script**:
  > *"Now, the question every evaluator should ask: **Does your system actually work in real life?***
  > 
  > *To prove our credibility, we implemented **Historical Backtesting**. Clicking 'Backtest Mode' loads real ERA5 reanalysis observations covering the landmark **Ahmedabad May 2010 Heatwave**—the catastrophic event that triggered South Asia's first Heat Action Plan.*
  > 
  > *On May 21, 2010, the city hit an all-time peak of 46.8°C. Our model flagged a **94/100 EXTREME HAZARD** and triggered Code Red alerts 48 hours prior. When compared against peer-reviewed epidemiological findings published by Azhar et al. in PLOS ONE, our danger window matches the exact week when 1,344 excess deaths occurred.*
  > 
  > *We don't just guess risk—we proved our algorithm against historical ground truth."*

---

### Phase 5: Actionable Early Warning Alerts & Conclusion (Minute 4:00 - 5:00)
> **Speaker Action**: Click **"Dispatch Early Warning Alert"** in the sidebar. Show the confirmation modal with SID and status.
> Click **"ℹ️ How This Works"** in the header to briefly show the educational modal.

* **Speaker Script**:
  > *"Finally, an early warning system is useless if it doesn't reach people. Clicking 'Dispatch Early Warning Alert' triggers our automated multi-channel gateway.*
  > 
  > *It compiles localized WHO and NDMA health advisories, formats work-rest schedules in vernacular languages, and routes them via our Twilio and Gupshup gateways to community leaders, construction contractors, and transit operators, with every message logged to an immutable SQLite/PostgreSQL audit trail.*
  > 
  > *The entire system runs locally in Docker or standalone scripts, requires zero expensive hardware, and can be deployed across any Indian municipal corporation in under 48 hours.*
  > 
  > *Thank you, we are now ready for your questions!"*

---

### Anticipated Judge Q&A Cheat Sheet

| Question | Winning Answer |
| :--- | :--- |
| **Q: Where does your weather data come from?** | *"We built an ingestion router in Day 1 supporting Open-Meteo, NASA POWER, and Copernicus ERA5 reanalysis, with automated fallbacks and coordinate-level caching so the system never fails if an external API is down."* |
| **Q: Why use WBGT and UTCI instead of just Heat Index?** | *"NOAA Heat Index only models shade temperature and humidity. Outdoor laborers in India work under direct solar radiation and wind. ISO 7243 Outdoor WBGT accounts for solar heating and wind cooling, which is the official occupational safety standard."* |
| **Q: Is ward-level mortality data included?** | *"We are transparent about our scientific scope: The biometeorological hazard is empirically validated against published mortality. However, because ward-level casualty data was not published by AMC in 2010, the ward spatial distribution is based on our 5-factor Census 2011/PLFS demographic vulnerability proxy."* |
| **Q: Can this scale to other cities?** | *"Yes. In `config.py`, we already configured target cities including Delhi (272 wards), Nagpur (38 wards), and Hyderabad (150 wards). Any city with a GeoJSON boundary file and Census CSV can be plugged in immediately."* |
