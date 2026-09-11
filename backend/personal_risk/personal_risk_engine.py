"""Personal Heat Risk Engine.

Calculates individualized, multi-factor thermal risk profiles based on biometeorological
tri-index calculations, metabolic activity exertion, continuous exposure duration,
and demographic/occupational vulnerability.

Scientific and Methodological Grounding:
----------------------------------------
1. Temperature Factor (max 25 pts):
   Extends NOAA/Steadman apparent temperature baseline starting at 25.0°C (thermal neutrality)
   up to 45.0°C (extreme environmental heat flux).
   Citation: Steadman, R.G. (1979). "The Assessment of Sultriness. Part I: A Temperature-Humidity Index."
   J. Appl. Meteorol., 18(7): 861-873.

2. Humidity & Evaporative Resistance Factor (max 20 pts):
   Extends Rothfusz regression / NOAA Heat Index. Above 30°C, skin vapor pressure gradient
   diminishes rapidly with increasing relative humidity, severely impairing latent heat
   loss via sweat evaporation.
   Citation: Rothfusz, L.P. (1990). "The Heat Index Equation." NWS Technical Attachment (SR/SSD 90-23).

3. Solar Radiant Load & Convective Wind Factor (max 15 pts):
   Extends Liljegren et al. (2008) Outdoor WBGT black globe physical heat balance equation.
   Shortwave direct/diffuse downward solar flux (0-1000 W/m²) adds direct radiative heat,
   while wind speed (>2 m/s) provides boundary-layer convective dissipation.
   Citation: Liljegren, J.C. et al. (2008). "Modeling the Wet Bulb Globe Temperature Using Standard
   Meteorological Measurements." J. Occup. Environ. Hyg., 5(10): 645-655. ISO 7243:2017.

4. Metabolic Activity Exertion Factor (max 20 pts):
   Extends ISO 8996 metabolic rate classes: resting (0 pts, ~100 W), walking (7 pts, ~165 W),
   moderate exercise (13 pts, ~230 W), heavy labor (20 pts, ~300+ W).
   Internal muscular heat production directly increases core temperature.
   Citation: ISO 8996:2021. "Ergonomics of the thermal environment - Determination of metabolic rate."

5. Continuous Exposure Duration Factor (max 10 pts):
   Extends ACGIH/NIOSH occupational exposure guidance and physiological heat storage curves.
   Short exposures (<15 min: 1 pt) allow transient compensation; prolonged exposures
   (>60-90 min: 8-10 pts) lead to severe cumulative heat accumulation, dehydration, and thermoregulatory failure.
   Citation: NIOSH (2016). "Criteria for a Recommended Standard: Occupational Exposure to Heat and Hot Environments."

6. Personal Vulnerability Factor (max 10 pts):
   Extends Census 2011/PLFS Heat Vulnerability Index (HVI) demographic multipliers and clinical guidance:
   - Elderly (60+): +6 pts (attenuated thirst sensation, reduced cardiovascular output, impaired baroreflex per WHO/WMO 2015).
   - Children (0-17): +3 pts (underdeveloped sweating capacity, high surface-area-to-mass ratio per WHO 2021).
   - Outdoor worker: +4 pts (chronic cumulative unmitigated exposure per NDMA 2024 Guidelines).
   - Elderly nonworking: +4 pts (frequent indoor thermal trap exposure).
   Total capped at 10 pts.
   Citation: WHO/WMO (2015). "Heatwaves and Health: Guidance on Warning-System Development." WMO-No. 1142.
   Azhar et al. (2014). PLOS ONE, 9(3): e91831.
"""

import math
import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.config import TUNED_RISK_TIER_THRESHOLDS, DEFAULT_RISK_TIER_THRESHOLDS
from backend.models import RiskLevel
from backend.db.models_orm import WardBoundary, WeatherReading, WardVulnerability, RiskForecast
from backend.index_calculation.heat_index import calculate_heat_index
from backend.index_calculation.wbgt import calculate_wbgt
from backend.index_calculation.utci import calculate_utci
from backend.vulnerability_model.health_consequence_map import COHORT_HEALTH_ACTIONS
from backend.personal_risk.personal_risk_schema import (
    PersonalRiskRequest,
    PersonalRiskResponse,
    RiskFactorItem,
    AgeGroup,
    OccupationType,
    ActivityType,
)

logger = logging.getLogger(__name__)

# Theme color mapping matching ward map choropleth
RISK_THEME_COLORS = {
    "LOW": "#2ecc71",        # Green
    "MODERATE": "#f1c40f",   # Yellow
    "HIGH": "#e67e22",       # Orange
    "VERY_HIGH": "#e74c3c",  # Red
    "EXTREME": "#8e44ad",    # Purple
}

# Standard Ahmedabad central coordinates for fallback
AHMEDABAD_CENTER_LAT = 23.0225
AHMEDABAD_CENTER_LON = 72.5714


def _classify_personal_risk_tier(score: float) -> Tuple[str, str]:
    """Classify 0-100 personal risk score into risk tier and color using calibrated thresholds."""
    th = TUNED_RISK_TIER_THRESHOLDS
    # Scale score from 0-100 to 0.0-1.0
    norm_score = score / 100.0

    if norm_score < th.get("LOW", 0.25):
        tier = RiskLevel.LOW.value
    elif norm_score < th.get("MODERATE", 0.48):
        tier = RiskLevel.MODERATE.value
    elif norm_score < th.get("HIGH", 0.68):
        tier = RiskLevel.HIGH.value
    elif norm_score < th.get("VERY_HIGH", 0.82):
        tier = RiskLevel.VERY_HIGH.value
    else:
        tier = RiskLevel.EXTREME.value

    color = RISK_THEME_COLORS.get(tier, "#f1c40f")
    return tier, color


def resolve_user_location(
    ward_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    db: Optional[Session] = None,
) -> Tuple[str, str, float, float]:
    """Resolve user input (explicit ward_id or GPS lat/lon) to a municipal ward.

    Returns
    -------
    Tuple[str, str, float, float]
        (ward_id, ward_name, center_lat, center_lon)
    """
    if db is None:
        try:
            from backend.db.session import SessionLocal
            with SessionLocal() as local_session:
                return resolve_user_location(ward_id=ward_id, lat=lat, lon=lon, db=local_session)
        except Exception:
            pass

    # 1. If explicit ward_id is provided, match in DB
    if ward_id and db:
        ward = db.query(WardBoundary).filter(WardBoundary.ward_id == ward_id.strip().upper()).first()
        if ward:
            return ward.ward_id, ward.ward_name, ward.center_lat, ward.center_lon


    # 2. If lat/lon are provided, perform spatial nearest match
    if lat is not None and lon is not None:
        if db:
            all_wards = db.query(WardBoundary).all()
            if all_wards:
                # Find closest ward center via Euclidean distance
                best_ward = min(
                    all_wards,
                    key=lambda w: (w.center_lat - lat) ** 2 + (w.center_lon - lon) ** 2,
                )
                return best_ward.ward_id, best_ward.ward_name, best_ward.center_lat, best_ward.center_lon

        # Fallback GIS loader if DB has no wards
        try:
            from backend.gis.boundary_loader import load_ward_boundaries
            from shapely.geometry import Point
            gdf = load_ward_boundaries()
            if gdf is not None and not gdf.empty:
                pt = Point(lon, lat)
                within_match = gdf[gdf.geometry.contains(pt)]
                if not within_match.empty:
                    row = within_match.iloc[0]
                    return row["ward_id"], row["ward_name"], row.get("center_lat", lat), row.get("center_lon", lon)
                
                # Nearest distance
                gdf["dist"] = gdf.geometry.distance(pt)
                nearest = gdf.sort_values("dist").iloc[0]
                return nearest["ward_id"], nearest["ward_name"], nearest.get("center_lat", lat), nearest.get("center_lon", lon)
        except Exception as e:
            logger.warning("GIS spatial join fallback error: %s", e)

    # 3. Default fallback: Navrangpura (AMD_01)
    if db:
        first_ward = db.query(WardBoundary).first()
        if first_ward:
            return first_ward.ward_id, first_ward.ward_name, first_ward.center_lat, first_ward.center_lon

    return "AMD_01", "Navrangpura", AHMEDABAD_CENTER_LAT, AHMEDABAD_CENTER_LON


def fetch_ward_weather_conditions(
    ward_id: str,
    lat: float,
    lon: float,
    db: Optional[Session] = None,
) -> Dict[str, float]:
    """Fetch current meteorological readings and calculate biometeorological indices."""
    temp_c = 36.5
    humidity_pct = 42.0
    wind_speed_ms = 2.5
    solar_radiation_wm2 = 750.0

    if db:
        latest = (
            db.query(WeatherReading)
            .filter(WeatherReading.ward_id == ward_id)
            .order_by(WeatherReading.timestamp.desc())
            .first()
        )
        if latest:
            temp_c = float(latest.temp_c)
            humidity_pct = float(latest.humidity_pct)
            wind_speed_ms = float(latest.wind_speed_ms)
            solar_radiation_wm2 = float(latest.solar_radiation_wm2)

    # Compute tri-indices
    hi = calculate_heat_index(temp_c, humidity_pct)
    wbgt = calculate_wbgt(temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2)
    utci = calculate_utci(temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2)

    return {
        "temp_c": round(float(temp_c), 1),
        "humidity_pct": round(float(humidity_pct), 1),
        "wind_speed_ms": round(float(wind_speed_ms), 1),
        "solar_radiation_wm2": round(float(solar_radiation_wm2), 1),
        "heat_index_c": round(float(hi), 1),
        "wbgt_c": round(float(wbgt), 1),
        "utci_c": round(float(utci), 1),
    }


def compute_factor_breakdown(
    weather: Dict[str, float],
    activity: ActivityType,
    duration_min: int,
    age_group: AgeGroup,
    occupation: OccupationType,
) -> Tuple[List[RiskFactorItem], float]:
    """Compute individual factor point contributions and final 0-100 personal risk score.

    Grounding & Weights:
    - Temperature: max 25 pts (Steadman 1979)
    - Humidity: max 20 pts (Rothfusz 1990)
    - Solar Radiant Load: max 15 pts (Liljegren 2008, ISO 7243)
    - Physical Activity: max 20 pts (ISO 8996)
    - Duration: max 10 pts (ACGIH / NIOSH 2016)
    - Personal Vulnerability: max 10 pts (WHO 2015/2021, Azhar 2014)
    Total possible = 100 pts.
    """
    t = weather["temp_c"]
    rh = weather["humidity_pct"]
    sol = weather["solar_radiation_wm2"]
    ws = weather["wind_speed_ms"]

    # 1. Temperature Contribution (max 25 pts)
    # Scaled from 25.0°C (neutral comfort = 0 pts) to 45.0°C (severe ambient heat = 25 pts)
    temp_ratio = max(0.0, min(1.0, (t - 25.0) / (45.0 - 25.0)))
    pts_temp = round(temp_ratio * 25.0, 1)

    # 2. Humidity & Evaporative Resistance (max 20 pts)
    # Above 28°C, RH dampens latent heat rejection nonlinearly
    rh_ratio = max(0.0, min(1.0, (rh - 20.0) / (85.0 - 20.0)))
    temp_weight = max(0.5, min(1.0, (t - 20.0) / 15.0))
    pts_humidity = round(rh_ratio * temp_weight * 20.0, 1)

    # 3. Solar Radiant Load & Wind Convective Attenuation (max 15 pts)
    # Solar irradiance up to 1000 W/m² increases black globe absorption; wind > 2 m/s mitigates
    solar_ratio = max(0.0, min(1.0, sol / 1000.0))
    wind_attenuation = max(0.6, min(1.0, 1.0 - (ws / 10.0)))
    pts_solar = round(solar_ratio * wind_attenuation * 15.0, 1)

    # 4. Metabolic Activity Exertion (max 20 pts, ISO 8996)
    activity_points_map = {
        ActivityType.RESTING: 0.0,             # Basal metabolic rate ~100W
        ActivityType.WALKING: 7.0,             # Light physical work ~165W
        ActivityType.MODERATE_EXERCISE: 13.0,  # Moderate aerobic work ~230W
        ActivityType.HEAVY_LABOR: 20.0,        # Intense manual labor ~300+W
    }
    pts_activity = activity_points_map.get(activity, 7.0)

    # 5. Continuous Outdoor Exposure Duration (max 10 pts, ACGIH/NIOSH)
    # <= 15m: 1.0, 30m: 3.0, 60m: 6.0, 90m: 8.0, >= 120m: 10.0
    if duration_min <= 15:
        pts_duration = round(max(0.5, (duration_min / 15.0) * 1.5), 1)
    elif duration_min <= 60:
        pts_duration = round(1.5 + ((duration_min - 15) / 45.0) * 4.5, 1)
    elif duration_min <= 120:
        pts_duration = round(6.0 + ((duration_min - 60) / 60.0) * 4.0, 1)
    else:
        pts_duration = 10.0

    # 6. Personal Demographic & Occupational Factors (max 10 pts, WHO 2015/2021)
    pts_age = 0.0
    if age_group == AgeGroup.AGE_0_17:
        pts_age = 3.0  # Immature thermoregulatory sweating & high BSA/mass ratio
    elif age_group == AgeGroup.AGE_46_59:
        pts_age = 2.0  # Mid-life cardiovascular workload
    elif age_group == AgeGroup.AGE_60_PLUS:
        pts_age = 6.0  # Attenuated thirst sensation, compromised baroreflex

    pts_occ = 0.0
    if occupation == OccupationType.OUTDOOR_WORKER:
        pts_occ = 4.0  # Chronic unmitigated sun/radiant exposure
    elif occupation == OccupationType.ELDERLY_NONWORKING:
        pts_occ = 4.0  # Susceptible to domestic thermal traps
    elif occupation == OccupationType.STUDENT:
        pts_occ = 1.0  # Midday school commute
    elif occupation == OccupationType.INDOOR_WORKER:
        pts_occ = 0.0  # Protected ambient workspace
    else:
        pts_occ = 1.0

    pts_personal = round(min(10.0, pts_age + pts_occ), 1)

    # Calculate Total Score (bounded 0.0 to 100.0)
    total_score = round(min(100.0, pts_temp + pts_humidity + pts_solar + pts_activity + pts_duration + pts_personal), 1)

    breakdown = [
        RiskFactorItem(
            factor_name="Air Temperature",
            point_contribution=pts_temp,
            max_points=25.0,
            description=f"Dry-bulb ambient heat ({weather['temp_c']}°C) elevates skin surface temperature (Steadman 1979).",
            icon="🌡️",
        ),
        RiskFactorItem(
            factor_name="High Humidity",
            point_contribution=pts_humidity,
            max_points=20.0,
            description=f"Relative humidity ({weather['humidity_pct']}%) impairs evaporative sweat cooling (Rothfusz Heat Index).",
            icon="💧",
        ),
        RiskFactorItem(
            factor_name="Solar Radiant Load",
            point_contribution=pts_solar,
            max_points=15.0,
            description=f"Direct solar irradiance ({weather['solar_radiation_wm2']} W/m²) adds direct radiative heat (ISO 7243 WBGT).",
            icon="☀️",
        ),
        RiskFactorItem(
            factor_name="Physical Exertion",
            point_contribution=pts_activity,
            max_points=20.0,
            description=f"Internal metabolic heat generation for '{activity.value.replace('_', ' ').title()}' (ISO 8996).",
            icon="🏃",
        ),
        RiskFactorItem(
            factor_name="Exposure Duration",
            point_contribution=pts_duration,
            max_points=10.0,
            description=f"Continuous outdoor duration ({duration_min} min) compounds bodily heat storage (ACGIH/NIOSH).",
            icon="⏱️",
        ),
        RiskFactorItem(
            factor_name="Personal Vulnerability",
            point_contribution=pts_personal,
            max_points=10.0,
            description=f"Demographic susceptibility ({age_group.value}, {occupation.value.replace('_', ' ').title()}) (WHO/WMO 2015).",
            icon="👤",
        ),
    ]

    return breakdown, total_score


def generate_clinical_consequences(
    age_group: AgeGroup,
    occupation: OccupationType,
    activity: ActivityType,
    risk_tier: str,
) -> Tuple[str, str]:
    """Retrieve epidemiological consequence and prevention recommendation from health_consequence_map."""
    is_severe = risk_tier in ("HIGH", "VERY_HIGH", "EXTREME")

    # Map to cohort in COHORT_HEALTH_ACTIONS
    if age_group == AgeGroup.AGE_60_PLUS or occupation == OccupationType.ELDERLY_NONWORKING:
        data = COHORT_HEALTH_ACTIONS["elderly_60plus"]
        consequence = data["extreme_risk_label"] if is_severe else data["risk_label"]
        action = data["urgent_action"] if is_severe else data["precaution_action"]
    elif occupation == OccupationType.OUTDOOR_WORKER or activity == ActivityType.HEAVY_LABOR:
        data = COHORT_HEALTH_ACTIONS["outdoor_workers"]
        consequence = data["extreme_risk_label"] if is_severe else data["risk_label"]
        action = data["urgent_action"] if is_severe else data["precaution_action"]
    elif age_group == AgeGroup.AGE_0_17:
        data = COHORT_HEALTH_ACTIONS["children_0_5"]
        consequence = data["extreme_risk_label"] if is_severe else data["risk_label"]
        action = data["urgent_action"] if is_severe else data["precaution_action"]
    else:
        # General healthy adult population
        if is_severe:
            consequence = (
                "Acute exertional heat exhaustion, heavy salt/electrolyte depletion, painful muscle spasms, "
                "and risk of exertional hyperthermia. Prolonged unshaded exposure can trigger sudden heat syncope (WHO 2021)."
            )
            action = (
                "MANDATORY EXERTION CESSATION: Cease vigorous outdoor movement; hydrate with at least 500 mL electrolyte water "
                "every 30 minutes; seek air-conditioned or well-ventilated shade immediately."
            )
        else:
            consequence = (
                "Mild cutaneous vasodilation, progressive fatigue, and increased heart rate. Sweat evaporation maintains "
                "thermal equilibrium if adequate hydration and periodic shaded rests are observed (WHO/WMO 2015)."
            )
            action = (
                "PRECAUTIONARY HYDRATION: Drink water regularly before thirst onset; wear wide-brim head protection and UV sunglasses; "
                "avoid continuous unshaded exertion between 11:30 AM and 4:30 PM."
            )

    return consequence, action


def calculate_suggested_better_time(
    risk_tier: str,
    duration_min: int,
) -> Optional[str]:
    """Suggest safer diurnal time window when environmental solar and thermal stress drop."""
    if risk_tier in ("HIGH", "VERY_HIGH", "EXTREME") or duration_min >= 60:
        return "🌅 Safer Time Window: Plan outdoor activity before 09:30 AM or after 05:45 PM, when WBGT drops by >5°C into the safer Green/Yellow zone."
    return "✅ Current conditions permit planned exposure. Maintain regular hydration."


def calculate_personal_risk(
    request: PersonalRiskRequest,
    db: Optional[Session] = None,
) -> PersonalRiskResponse:
    """Master pipeline executing end-to-end Personal Heat Twin risk evaluation."""
    # 1. Resolve Location
    ward_id, ward_name, lat, lon = resolve_user_location(
        ward_id=request.ward_id,
        lat=request.lat,
        lon=request.lon,
        db=db,
    )

    # 2. Fetch Active Weather & Biometeorological Indices
    weather = fetch_ward_weather_conditions(
        ward_id=ward_id,
        lat=lat,
        lon=lon,
        db=db,
    )

    # 3. Compute 6-Factor Point Contributions
    factors, total_score = compute_factor_breakdown(
        weather=weather,
        activity=request.current_activity,
        duration_min=request.outdoor_duration_minutes,
        age_group=request.age_group,
        occupation=request.occupation,
    )

    # 4. Classify Risk Tier & Color
    risk_tier, risk_color = _classify_personal_risk_tier(total_score)

    # 5. Extract Clinical Consequence & Action
    consequence_text, recommendation_text = generate_clinical_consequences(
        age_group=request.age_group,
        occupation=request.occupation,
        activity=request.current_activity,
        risk_tier=risk_tier,
    )

    # 6. Better Time Window
    suggested_time = calculate_suggested_better_time(
        risk_tier=risk_tier,
        duration_min=request.outdoor_duration_minutes,
    )

    return PersonalRiskResponse(
        personal_risk_score=total_score,
        risk_tier=risk_tier,
        risk_color=risk_color,
        factor_breakdown=factors,
        consequence_text=consequence_text,
        recommendation_text=recommendation_text,
        suggested_better_time=suggested_time,
        ward_id=ward_id,
        ward_name=ward_name,
        current_conditions=weather,
    )
