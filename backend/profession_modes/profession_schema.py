"""Pydantic Schemas for Profession Modes.

Defines schemas for mode metadata, hourly risk points, and the consolidated
profession mode risk response.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    """Actionable clinical or occupational advice item."""

    action_text: str = Field(..., description="Actionable recommendation sentence")
    action_type: str = Field(default="precaution", description="'precaution' or 'urgent'")
    citation: Optional[str] = Field(default=None, description="Epidemiological guideline source")
    icon: str = Field(default="⚡", description="Visual indicator emoji")


class HourlyRiskPoint(BaseModel):
    """Single hour projection in the forward timeline."""

    hour_offset: int = Field(..., ge=0, description="Hours ahead from now (0 = current hour)")
    hour_label: str = Field(..., description="Short hour label e.g. '12 PM'")
    hour_range: str = Field(..., description="Hourly time range e.g. '12:00 PM - 1:00 PM'")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Calculated personal heat risk score (0-100)")
    risk_tier: str = Field(..., description="Categorical risk tier: LOW, MODERATE, HIGH, VERY_HIGH, EXTREME")
    risk_color: str = Field(..., description="Hex color matching existing dashboard theme")
    temp_c: float = Field(..., description="Forecasted ambient air temperature in °C")
    wbgt_c: float = Field(..., description="Forecasted Outdoor Wet Bulb Globe Temperature in °C")
    heat_index_c: float = Field(..., description="Forecasted NOAA Heat Index in °C")
    utci_c: float = Field(..., description="Forecasted Universal Thermal Climate Index in °C")


class ProfessionModeDetail(BaseModel):
    """Overview metadata for a single profession mode."""

    mode_id: str = Field(..., description="Machine identifier (e.g. 'farmer', 'delivery_worker')")
    display_name: str = Field(..., description="Human-readable title (e.g. 'Farmer')")
    icon: str = Field(..., description="Mode emoji icon")
    subtitle: str = Field(..., description="Target cohort description")
    description: str = Field(..., description="Occupational thermal exposure profile")


class ProfessionModeResponse(BaseModel):
    """Consolidated response for a selected profession mode and location."""

    mode_id: str
    display_name: str
    icon: str
    subtitle: str
    ward_id: str
    ward_name: str
    current_risk_score: float = Field(..., ge=0.0, le=100.0)
    current_risk_tier: str
    current_risk_color: str
    current_temp_c: float
    current_wbgt_c: float
    peak_hour_range: str
    peak_risk_score: float
    peak_risk_tier: str
    hourly_breakdown: List[HourlyRiskPoint]
    recommendations: List[RecommendationItem]
