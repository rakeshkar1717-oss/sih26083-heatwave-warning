"""Profession Modes Subsystem.

Curated role-specific heat stress forecasts and clinical recommendations.
"""

from backend.profession_modes.mode_config import PROFESSION_MODES_CONFIG
from backend.profession_modes.profession_schema import (
    HourlyRiskPoint,
    ProfessionModeDetail,
    ProfessionModeResponse,
    RecommendationItem,
)
from backend.profession_modes.hourly_risk_engine import (
    get_hourly_risk_forecast,
    simulate_diurnal_hourly_weather,
)

__all__ = [
    "PROFESSION_MODES_CONFIG",
    "HourlyRiskPoint",
    "ProfessionModeDetail",
    "ProfessionModeResponse",
    "RecommendationItem",
    "get_hourly_risk_forecast",
    "simulate_diurnal_hourly_weather",
]
