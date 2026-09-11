"""Pydantic schemas for the Personal Heat Twin risk calculation engine.

Standardizes inputs and structured outputs for personalized thermal strain assessments.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class AgeGroup(str, Enum):
    """Demographic age cohorts with distinct physiological thermoregulatory capacity."""
    AGE_0_17 = "0-17"
    AGE_18_30 = "18-30"
    AGE_31_45 = "31-45"
    AGE_46_59 = "46-59"
    AGE_60_PLUS = "60+"


class OccupationType(str, Enum):
    """Occupational exposure categories."""
    STUDENT = "student"
    OUTDOOR_WORKER = "outdoor_worker"
    INDOOR_WORKER = "indoor_worker"
    ELDERLY_NONWORKING = "elderly_nonworking"
    OTHER = "other"


class ActivityType(str, Enum):
    """Metabolic activity levels based on ISO 8996 physical exertion standards."""
    RESTING = "resting"
    WALKING = "walking"
    MODERATE_EXERCISE = "moderate_exercise"
    HEAVY_LABOR = "heavy_labor"


class PersonalRiskRequest(BaseModel):
    """Request payload submitted by a user for personalized heat risk calculation."""

    age_group: AgeGroup = Field(..., description="Age group of the individual")
    occupation: OccupationType = Field(..., description="Primary occupation or employment type")
    current_activity: ActivityType = Field(..., description="Planned or current physical activity")
    outdoor_duration_minutes: int = Field(
        ...,
        ge=0,
        le=720,
        description="Estimated continuous outdoor exposure in minutes (0 to 12 hours)",
    )
    ward_id: Optional[str] = Field(
        default=None,
        description="Municipal ward identifier (e.g. 'AMD_01' for Navrangpura)",
    )
    lat: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Optional GPS latitude for auto-resolving nearest ward",
    )
    lon: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Optional GPS longitude for auto-resolving nearest ward",
    )

    @field_validator("outdoor_duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Outdoor duration cannot be negative.")
        if v > 720:
            raise ValueError("Outdoor duration cannot exceed 720 minutes (12 hours).")
        return v


class RiskFactorItem(BaseModel):
    """Individual contributing factor to the composite 0-100 personal heat risk score."""

    factor_name: str = Field(..., description="Human-readable factor title (e.g. 'Air Temperature')")
    point_contribution: float = Field(..., description="Points added to personal risk score (positive contribution)")
    max_points: float = Field(..., description="Theoretical maximum points for this factor")
    description: str = Field(..., description="Brief physical or epidemiological rationale")
    icon: str = Field(default="⚡", description="Visual display icon or emoji")


class PersonalRiskResponse(BaseModel):
    """Structured response containing personal risk score, factor breakdown, and clinical advice."""

    personal_risk_score: float = Field(..., ge=0.0, le=100.0, description="Composite personal risk score (0-100)")
    risk_tier: str = Field(..., description="Categorical risk tier: LOW, MODERATE, HIGH, VERY_HIGH, EXTREME")
    risk_color: str = Field(..., description="Hex color matching existing dashboard theme")
    factor_breakdown: List[RiskFactorItem] = Field(..., description="Point contributions per factor (sums to score)")
    consequence_text: str = Field(..., description="Specific epidemiological/clinical consequence for this profile")
    recommendation_text: str = Field(..., description="Actionable clinical or occupational prevention measures")
    suggested_better_time: Optional[str] = Field(
        default=None,
        description="Safer diurnal time window recommendation if current risk is elevated",
    )
    ward_id: str = Field(..., description="Resolved municipal ward ID")
    ward_name: str = Field(..., description="Resolved municipal ward name")
    current_conditions: Dict[str, Any] = Field(
        ...,
        description="Active meteorological conditions: temp_c, humidity_pct, heat_index_c, wbgt_c, utci_c",
    )
