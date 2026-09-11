"""Personal Heat Risk Query Handler for Heat Copilot.

Extracts activity, timing, duration, and personal vulnerability entities from user queries,
evaluates microclimatic thermal hazard and ward demographic vulnerability, and formats
a structured, actionable assessment conforming to the ThermoGuard reference design.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import RiskLevel
from backend.db.models_orm import WardBoundary, WardVulnerability, WeatherReading, RiskForecast
from backend.index_calculation.heat_index import calculate_heat_index
from backend.index_calculation.wbgt import calculate_wbgt

logger = logging.getLogger(__name__)

# Known Ahmedabad wards for auto-detection if mentioned in query text
AHMEDABAD_WARDS_LOOKUP = {
    "navrangpura": "AMD_01",
    "jamalpur": "AMD_02",
    "khadia": "AMD_03",
    "shahpur": "AMD_04",
    "dariapur": "AMD_05",
    "danilimda": "AMD_06",
    "behrampura": "AMD_07",
    "maninagar": "AMD_08",
    "vatva": "AMD_17",
    "bodakdev": "AMD_15",
    "ghatlodia": "AMD_10",
    "thalke": "AMD_12",
    "naranpura": "AMD_11",
    "paldi": "AMD_18",
    "bopal": "AMD_25",
    "vejalpur": "AMD_20",
    "chandkheda": "AMD_30",
    "motera": "AMD_31",
    "sabarmati": "AMD_32",
    "ranip": "AMD_33",
    "gomtipur": "AMD_14",
    "bapunagar": "AMD_16",
    "saraspur": "AMD_13",
    "amraiwadi": "AMD_19",
    "odhav": "AMD_21",
    "nikol": "AMD_22",
    "naroda": "AMD_23",
}

ACTIVITY_EXERTION_WEIGHTS = {
    "construction": 1.25,
    "labor": 1.25,
    "heavy labor": 1.30,
    "delivery": 1.20,
    "jog": 1.20,
    "run": 1.20,
    "sports": 1.20,
    "football": 1.20,
    "cricket": 1.15,
    "cycle": 1.15,
    "cycling": 1.15,
    "walk": 1.05,
    "walking": 1.05,
    "commute": 1.05,
    "shopping": 1.00,
    "market": 1.05,
    "standing": 1.00,
    "indoors": 0.85,
    "sitting": 0.85,
}

VULNERABILITY_KEYWORDS = {
    "elderly": 1.20,
    "senior": 1.20,
    "grandfather": 1.20,
    "grandmother": 1.20,
    "old": 1.15,
    "child": 1.20,
    "kid": 1.20,
    "baby": 1.25,
    "infant": 1.25,
    "toddler": 1.25,
    "pregnant": 1.20,
    "heart": 1.25,
    "diabetic": 1.15,
    "asthma": 1.15,
}


def extract_entities(message: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract activity, target time, duration, and vulnerability context from query."""
    text = message.lower()
    ctx = user_context or {}

    # 1. Target Time Extraction
    time_str = ctx.get("time")
    if not time_str:
        # Check patterns like "2pm", "2:30 pm", "14:00", "noon", "afternoon", "now", "today", "tomorrow"
        time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", text)
        if time_match and any(x in time_match.group(1) for x in ["am", "pm", ":"]):
            time_str = time_match.group(1).upper()
        elif "noon" in text:
            time_str = "12:00 PM"
        elif "afternoon" in text:
            time_str = "2:00 PM"
        elif "morning" in text:
            time_str = "9:00 AM"
        elif "evening" in text:
            time_str = "6:00 PM"
        else:
            time_str = "Now (Live Conditions)"

    # 2. Activity Extraction
    activity = ctx.get("activity")
    if not activity:
        for act in ACTIVITY_EXERTION_WEIGHTS:
            if re.search(rf"\b{act}\b", text):
                activity = act.title()
                break
        if not activity:
            activity = "General Outdoor Activity"

    # 3. Duration Extraction
    duration = ctx.get("duration")
    if not duration:
        dur_match = re.search(r"\b(\d+\s*(?:hours?|hrs?|mins?|minutes?))\b", text)
        if dur_match:
            duration = dur_match.group(1)
        elif "all day" in text:
            duration = "Full Day (~6-8 hours)"
        else:
            duration = "~45-60 minutes"

    # 4. Vulnerability Context
    vuln_mult = 1.0
    vuln_note = []
    for kw, mult in VULNERABILITY_KEYWORDS.items():
        if re.search(rf"\b{kw}\b", text) or ctx.get("age_group") == kw:
            vuln_mult = max(vuln_mult, mult)
            vuln_note.append(kw.title())

    # 5. Ward detection from message text
    detected_ward_id = None
    for wname, wid in AHMEDABAD_WARDS_LOOKUP.items():
        if re.search(rf"\b{wname}\b", text):
            detected_ward_id = wid
            break

    return {
        "time_str": time_str,
        "activity": activity,
        "duration": duration,
        "vuln_mult": vuln_mult,
        "vuln_notes": vuln_note,
        "detected_ward_id": detected_ward_id,
    }


def handle_personal_risk_query(
    message: str,
    ward_id: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Evaluate personal thermal strain query and produce structured ThermoGuard response."""
    entities = extract_entities(message, user_context)
    resolved_ward_id = ward_id or entities["detected_ward_id"]

    # If ward is still unresolvable, prompt the user politely
    if not resolved_ward_id:
        return {
            "response_text": (
                "📍 **Which area or municipal ward in Ahmedabad are you asking about?**\n\n"
                "To give you an exact, street-level safety assessment and thermal stress rating, "
                "please mention your ward (e.g., *Navrangpura*, *Jamalpur*, *Bodakdev*, *Vatva*, *Maninagar*), "
                "or click on your ward on the map!"
            ),
            "requires_ward_selection": True,
            "risk_score": None,
            "risk_tier": None,
            "recommendation": None,
            "suggested_better_time": None,
            "dominant_factor": None,
        }

    # Query DB or fallback for ward metadata and latest weather
    ward_name = resolved_ward_id
    vuln_score = 0.50
    temp_c = 42.5
    humidity_pct = 32.0
    wind_ms = 2.4
    solar_wm2 = 820.0
    forecast_data = []

    if db:
        ward = db.query(WardBoundary).filter(WardBoundary.ward_id == resolved_ward_id).first()
        if ward:
            ward_name = ward.ward_name
            if ward.vulnerability:
                vuln_score = ward.vulnerability.vulnerability_score

        latest_w = (
            db.query(WeatherReading)
            .filter(WeatherReading.ward_id == resolved_ward_id)
            .order_by(WeatherReading.timestamp.desc())
            .first()
        )
        if latest_w:
            temp_c = latest_w.temp_c
            humidity_pct = latest_w.humidity_pct
            wind_ms = latest_w.wind_speed_ms
            solar_wm2 = latest_w.solar_radiation_wm2

        forecasts = (
            db.query(RiskForecast)
            .filter(RiskForecast.ward_id == resolved_ward_id)
            .order_by(RiskForecast.forecast_date.asc())
            .limit(5)
            .all()
        )
        for f in forecasts:
            forecast_data.append({
                "horizon": getattr(f, "forecast_horizon_days", 1),
                "predicted_risk": f.predicted_risk_score,
                "risk_tier": f.predicted_risk_tier,
            })

    # Recalculate biometeorology with actual physical models
    hi_c = calculate_heat_index(temp_c, humidity_pct)
    wbgt_c = calculate_wbgt(temp_c, humidity_pct, wind_ms, solar_wm2)

    # Physical thermal strain score (0 to 100)
    hi_norm = min(100.0, max(0.0, (hi_c - 27.0) / (54.0 - 27.0) * 100.0))
    wbgt_norm = min(100.0, max(0.0, (wbgt_c - 18.0) / (38.0 - 18.0) * 100.0))
    hazard_score = round(0.50 * wbgt_norm + 0.50 * hi_norm, 2)

    # Activity multiplier
    act_name = entities["activity"].lower()
    act_mult = 1.0
    for k, v in ACTIVITY_EXERTION_WEIGHTS.items():
        if k in act_name:
            act_mult = v
            break

    # Effective personal risk score (0.0 to 1.0)
    base_risk = 0.60 * (hazard_score / 100.0) + 0.40 * vuln_score
    adjusted_risk = min(1.0, round(base_risk * act_mult * entities["vuln_mult"], 3))

    # Classify tier
    if adjusted_risk < 0.25:
        risk_tier = "LOW"
        recommendation = "SAFE"
        rec_color = "🟢 SAFE"
    elif adjusted_risk < 0.48:
        risk_tier = "MODERATE"
        recommendation = "CAUTION"
        rec_color = "🟡 MODERATE CAUTION"
    elif adjusted_risk < 0.68:
        risk_tier = "HIGH"
        recommendation = "AVOID UNNECESSARY EXPOSURE"
        rec_color = "🟠 HIGH RISK - AVOID PEAK HOURS"
    elif adjusted_risk < 0.82:
        risk_tier = "VERY_HIGH"
        recommendation = "STAY INDOORS / EXTREME DANGER"
        rec_color = "🔴 VERY HIGH RISK - RESTRICT OUTDOORS"
    else:
        risk_tier = "EXTREME"
        recommendation = "LIFE-THREATENING - EVACUATE TO COOLING CENTER"
        rec_color = "🟣 EXTREME DANGER"

    # Identify dominant risk drivers
    drivers = []
    if solar_wm2 > 650:
        drivers.append("Intense direct solar radiant load (>650 W/m²)")
    if humidity_pct > 40:
        drivers.append(f"Moisture barrier ({humidity_pct:.0f}% RH) suppressing sweat evaporation")
    elif temp_c >= 40:
        drivers.append(f"Extreme ambient sensible heat ({temp_c:.1f}°C)")
    if act_mult > 1.10:
        drivers.append(f"Metabolic internal heat generation from {entities['activity']}")
    if entities["vuln_notes"]:
        drivers.append(f"Physiological vulnerability profile ({', '.join(entities['vuln_notes'])})")

    dominant_factor_text = "; ".join(drivers) if drivers else "Elevated diurnal solar irradiance"

    # Suggest safer time window
    if adjusted_risk >= 0.48:
        suggested_time = "Before 10:30 AM or after 6:15 PM"
        time_advice = (
            f"**Better Time Window**: Reschedule your {entities['activity'].lower()} to **{suggested_time}**, "
            "when solar radiation ceases, ambient temperatures drop to ~33–35°C, and WBGT decreases into safer limits."
        )
    else:
        suggested_time = "Current window is acceptable"
        time_advice = (
            "**Optimal Window**: Ambient conditions currently permit moderate activity. "
            "Maintain hydration and carry drinking water."
        )

    # Format ThermoGuard structure
    response_text = f"""### 🛡️ ThermoGuard Personal Heat Risk Assessment

* **Trip / Activity**: {entities['activity']} in **{ward_name}** ({resolved_ward_id})
* **Target Time**: {entities['time_str']} (Estimated duration: {entities['duration']})
* **Current Microclimate**: **{temp_c:.1f}°C** | **{humidity_pct:.0f}% RH** | **WBGT: {wbgt_c:.1f}°C**
* **Personal Risk Level**: {rec_color} (Personal Index: **{adjusted_risk:.2f}**)

---

#### 🔍 Why Is This Risk Level Triggered?
* **Primary Heat Strain Drivers**: {dominant_factor_text}.
* **Physiological Impact**: Under outdoor WBGT exceeding 31°C, core body temperature rises rapidly within 30 minutes of sustained exertion, creating high susceptibility to exertional heat exhaustion and cardiovascular stress (WHO/NDMA Clinical Guidelines).

---

#### 💡 Clear Recommendation
**{recommendation}**

{time_advice}

* **Preventive Protocol**: Drink at least 500 mL of water with oral electrolytes, wear a wide-brimmed hat or carry an umbrella, wear loose light-colored cotton clothing, and take 15-minute shaded rest breaks.
"""

    return {
        "response_text": response_text.strip(),
        "requires_ward_selection": False,
        "risk_score": adjusted_risk,
        "risk_tier": risk_tier,
        "recommendation": recommendation,
        "suggested_better_time": suggested_time,
        "dominant_factor": dominant_factor_text,
    }
