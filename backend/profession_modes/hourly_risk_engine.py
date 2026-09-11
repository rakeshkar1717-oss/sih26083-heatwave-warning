"""Hourly Risk Trajectory Engine for Profession Modes.

Interpolates and predicts high-resolution forward hourly thermal strain trajectories
for specific occupational and demographic presets.

Reuses:
- backend.personal_risk.personal_risk_engine (compute_factor_breakdown, _classify_personal_risk_tier, resolve_user_location)
- backend.index_calculation (calculate_wbgt, calculate_heat_index, calculate_utci)
- backend.profession_modes.mode_config (PROFESSION_MODES_CONFIG)
"""

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.config import TUNED_RISK_TIER_THRESHOLDS
from backend.models import RiskLevel
from backend.index_calculation.heat_index import calculate_heat_index
from backend.index_calculation.wbgt import calculate_wbgt
from backend.index_calculation.utci import calculate_utci
from backend.personal_risk.personal_risk_engine import (
    resolve_user_location,
    fetch_ward_weather_conditions,
    compute_factor_breakdown,
    _classify_personal_risk_tier,
)
from backend.profession_modes.mode_config import PROFESSION_MODES_CONFIG
from backend.profession_modes.profession_schema import (
    HourlyRiskPoint,
    ProfessionModeResponse,
    RecommendationItem,
)

logger = logging.getLogger(__name__)


def _format_hour_label(hour_24: int) -> Tuple[str, str]:
    """Format 24-hour integer into 12-hour label and 1-hour range."""
    h_start = hour_24 % 24
    h_end = (h_start + 1) % 24

    def _fmt(h: int) -> str:
        if h == 0:
            return "12 AM"
        elif h < 12:
            return f"{h} AM"
        elif h == 12:
            return "12 PM"
        else:
            return f"{h - 12} PM"

    start_str = _fmt(h_start)
    end_str = _fmt(h_end)
    label = start_str
    hour_range = f"{start_str} - {end_str}"
    return label, hour_range


def simulate_diurnal_hourly_weather(
    base_weather: Dict[str, float],
    hours_ahead: int = 5,
    start_hour: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Generate physically grounded diurnal hourly meteorological trajectory for the next N hours.

    Approximation Method:
    --------------------
    1. Solar Zenith & Daylight Solar Radiation:
       Models daytime downward solar irradiance via solar hour sine curve peaking at 13:00 (~920 W/m²),
       zero between 19:30 and 06:30.
    2. Temperature Thermal Lag:
       Ambient dry-bulb temperature peaks 2 hours after solar noon (~15:00) and bottoms at dawn (~05:30).
       Diurnal temperature swing in Ahmedabad summer is typically 8°C to 12°C.
    3. Relative Humidity Inversion:
       Relative humidity varies inversely with ambient temperature, reaching daily minimum in mid-afternoon.
    """
    now = datetime.now()
    cur_hour = start_hour if start_hour is not None else now.hour

    hourly_records = []
    base_temp = base_weather["temp_c"]
    base_rh = base_weather["humidity_pct"]
    base_ws = base_weather["wind_speed_ms"]

    for offset in range(hours_ahead + 1):
        target_hour = (cur_hour + offset) % 24
        label, hour_range = _format_hour_label(target_hour)

        # Diurnal solar factor: 0.0 to 1.0 (peaks at 13:00)
        if 7.0 <= target_hour <= 19.0:
            solar_sin = math.sin((target_hour - 7.0) * math.pi / 12.0)
            solar_factor = max(0.0, solar_sin)
        else:
            solar_factor = 0.0

        # Diurnal temp factor: peaks at 15:00 (approx 2h lag after solar peak)
        if 6.0 <= target_hour <= 20.0:
            temp_sin = math.sin((target_hour - 6.0) * math.pi / 14.0)
            temp_factor = max(0.0, temp_sin)
        else:
            temp_factor = -0.3

        # Compute hourly weather adjustments
        # When current hour is known, anchor hour 0 exactly to base_weather
        if offset == 0:
            temp_c = base_temp
            rh = base_rh
            ws = base_ws
            solar = base_weather["solar_radiation_wm2"]
        else:
            # Model relative swing from baseline
            # Current hour baseline factor
            cur_temp_factor = max(0.0, math.sin((cur_hour - 6.0) * math.pi / 14.0)) if 6.0 <= cur_hour <= 20.0 else -0.3
            delta_factor = temp_factor - cur_temp_factor
            temp_c = round(base_temp + (delta_factor * 8.0), 1)
            temp_c = max(24.0, min(48.0, temp_c))

            rh = round(base_rh - (delta_factor * 16.0), 1)
            rh = max(15.0, min(85.0, rh))

            ws = round(max(0.8, base_ws + (0.5 * solar_factor)), 1)
            solar = round(920.0 * solar_factor, 1)

        # Calculate tri-indices for this hour
        hi = calculate_heat_index(temp_c, rh)
        wbgt = calculate_wbgt(temp_c, rh, ws, solar)
        utci = calculate_utci(temp_c, rh, ws, solar)

        hourly_records.append({
            "hour_offset": offset,
            "hour_24": target_hour,
            "hour_label": label,
            "hour_range": hour_range,
            "temp_c": round(float(temp_c), 1),
            "humidity_pct": round(float(rh), 1),
            "wind_speed_ms": round(float(ws), 1),
            "solar_radiation_wm2": round(float(solar), 1),
            "heat_index_c": round(float(hi), 1),
            "wbgt_c": round(float(wbgt), 1),
            "utci_c": round(float(utci), 1),
        })

    return hourly_records


def get_hourly_risk_forecast(
    mode_id: str,
    ward_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    hours_ahead: int = 5,
    start_hour: Optional[int] = None,
    db: Optional[Session] = None,
) -> ProfessionModeResponse:
    """Evaluate hour-by-hour heat risk trajectory and mode-tailored recommendations.

    Parameters
    ----------
    mode_id : str
        One of the 6 canonical profession modes ('student', 'delivery_worker', etc.)
    ward_id : Optional[str]
        Municipal ward ID (e.g. 'AMD_01')
    lat, lon : Optional[float]
        GPS coordinates to resolve nearest ward
    hours_ahead : int
        Number of forward projection hours (default is 5)
    start_hour : Optional[int]
        Simulated starting hour (0-23), default uses system clock
    db : Optional[Session]
        SQLAlchemy database session
    """
    mode_key = mode_id.strip().lower()
    if mode_key not in PROFESSION_MODES_CONFIG:
        valid_modes = list(PROFESSION_MODES_CONFIG.keys())
        raise ValueError(f"Unknown profession mode '{mode_id}'. Must be one of: {valid_modes}")

    config = PROFESSION_MODES_CONFIG[mode_key]
    mapping = config["activity_mapping"]

    # 1. Resolve Location
    resolved_ward_id, resolved_ward_name, center_lat, center_lon = resolve_user_location(
        ward_id=ward_id,
        lat=lat,
        lon=lon,
        db=db,
    )

    # 2. Fetch Base Ward Weather
    base_weather = fetch_ward_weather_conditions(
        ward_id=resolved_ward_id,
        lat=center_lat,
        lon=center_lon,
        db=db,
    )

    # 3. Simulate Diurnal Hourly Weather for the next N hours
    hourly_weather_list = simulate_diurnal_hourly_weather(
        base_weather=base_weather,
        hours_ahead=hours_ahead,
        start_hour=start_hour,
    )

    # 4. Evaluate Personal Risk Engine for each hour
    hourly_points: List[HourlyRiskPoint] = []
    for h in hourly_weather_list:
        w_dict = {
            "temp_c": h["temp_c"],
            "humidity_pct": h["humidity_pct"],
            "wind_speed_ms": h["wind_speed_ms"],
            "solar_radiation_wm2": h["solar_radiation_wm2"],
        }

        # Reuse existing personal risk calculation engine
        factors, score = compute_factor_breakdown(
            weather=w_dict,
            activity=mapping["current_activity"],
            duration_min=mapping["outdoor_duration_minutes"],
            age_group=mapping["age_group"],
            occupation=mapping["occupation"],
        )

        tier, color = _classify_personal_risk_tier(score)

        hourly_points.append(
            HourlyRiskPoint(
                hour_offset=h["hour_offset"],
                hour_label=h["hour_label"],
                hour_range=h["hour_range"],
                risk_score=score,
                risk_tier=tier,
                risk_color=color,
                temp_c=h["temp_c"],
                wbgt_c=h["wbgt_c"],
                heat_index_c=h["heat_index_c"],
                utci_c=h["utci_c"],
            )
        )

    # 5. Extract Current and Peak Values
    current_pt = hourly_points[0]
    peak_pt = max(hourly_points, key=lambda x: x.risk_score)

    # 6. Filter & Prioritize Mode Recommendations
    # If peak or current risk is severe (HIGH / VERY_HIGH / EXTREME), prioritize urgent actions first
    is_severe = peak_pt.risk_tier in ("HIGH", "VERY_HIGH", "EXTREME")
    raw_recs = config["default_recommendations"]

    if is_severe:
        sorted_recs = sorted(raw_recs, key=lambda r: 0 if r["action_type"] == "urgent" else 1)
    else:
        sorted_recs = sorted(raw_recs, key=lambda r: 0 if r["action_type"] == "precaution" else 1)

    recommendations = [
        RecommendationItem(
            action_text=r["action_text"],
            action_type=r["action_type"],
            citation=r.get("citation"),
            icon=r.get("icon", "⚡"),
        )
        for r in sorted_recs
    ]

    return ProfessionModeResponse(
        mode_id=config["mode_id"],
        display_name=config["display_name"],
        icon=config["icon"],
        subtitle=config["subtitle"],
        ward_id=resolved_ward_id,
        ward_name=resolved_ward_name,
        current_risk_score=current_pt.risk_score,
        current_risk_tier=current_pt.risk_tier,
        current_risk_color=current_pt.risk_color,
        current_temp_c=current_pt.temp_c,
        current_wbgt_c=current_pt.wbgt_c,
        peak_hour_range=peak_pt.hour_range,
        peak_risk_score=peak_pt.risk_score,
        peak_risk_tier=peak_pt.risk_tier,
        hourly_breakdown=hourly_points,
        recommendations=recommendations,
    )
