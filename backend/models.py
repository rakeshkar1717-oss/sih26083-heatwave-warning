"""Shared data models, enumerations, and validation schemas for SIH26083.

Every module across the entire project (data ingestion, thermal indices, vulnerability,
GIS, API, and alerts) MUST import its shared types from this file.
Do NOT create parallel schemas in other modules.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# 1. Weather Data Ingestion Schema (Fixed Column Contract)
# ==============================================================================

FIXED_WEATHER_COLUMNS: List[str] = [
    "timestamp",
    "lat",
    "lon",
    "temp_c",
    "humidity_pct",
    "wind_speed_ms",
    "solar_radiation_wm2",
    "source",
]


class WeatherSource(str, Enum):
    """Supported meteorological data providers."""
    OPEN_METEO = "open_meteo"
    NASA_POWER = "nasa_power"
    ERA5 = "era5"
    FUSED_OM_NASA = "fused_om_nasa"


class WeatherRecord(BaseModel):
    """Pydantic model representing a single standardized hourly weather record."""

    timestamp: datetime = Field(..., description="Observation timestamp in UTC")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    temp_c: float = Field(..., ge=-60.0, le=70.0, description="Air temperature at 2m in Celsius")
    humidity_pct: float = Field(..., ge=0.0, le=100.0, description="Relative humidity in percentage (0-100)")
    wind_speed_ms: float = Field(..., ge=0.0, le=150.0, description="Wind speed at 10m in meters per second")
    solar_radiation_wm2: float = Field(..., ge=0.0, le=2000.0, description="Surface solar radiation downward in W/m²")
    source: WeatherSource = Field(..., description="Data provider identifier")

    # Optional biometeorological indices (appended by Day 2 index_engine)
    heat_index_c: Optional[float] = Field(default=None, description="NOAA/OSHA Heat Index in Celsius")
    wbgt_c: Optional[float] = Field(default=None, description="Outdoor Wet Bulb Globe Temperature in Celsius")
    utci_c: Optional[float] = Field(default=None, description="Universal Thermal Climate Index in Celsius")
    thermal_stress_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Composite 0-100 thermal hazard score")
    stress_category: Optional[str] = Field(default=None, description="Hazard category description")


def validate_weather_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate that a pandas DataFrame strictly conforms to the fixed weather schema.

    Parameters
    ----------
    df : pd.DataFrame
        Candidate meteorological dataframe.

    Returns
    -------
    pd.DataFrame
        The validated dataframe with correct column order and parsed timestamp types.

    Raises
    ------
    ValueError
        If any required column is missing, unknown columns are present, or types are invalid.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("Provided data is not a valid pandas DataFrame.")

    # Check for missing required columns
    missing_cols = [c for c in FIXED_WEATHER_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Weather DataFrame is missing required column(s): {missing_cols}. "
            f"Expected exact columns: {FIXED_WEATHER_COLUMNS}"
        )

    # Ensure fixed canonical columns come first, and preserve extra metadata columns
    extra_cols = [c for c in df.columns if c not in FIXED_WEATHER_COLUMNS]
    df_ordered = df[FIXED_WEATHER_COLUMNS + extra_cols].copy()

    # Empty dataframes are allowed if valid columns exist, but type check non-empty
    if df_ordered.empty:
        return df_ordered

    # Ensure timestamp is datetime or parseable ISO string
    if not pd.api.types.is_datetime64_any_dtype(df_ordered["timestamp"]):
        try:
            df_ordered["timestamp"] = pd.to_datetime(df_ordered["timestamp"], utc=True)
        except Exception as e:
            raise ValueError(f"Failed to parse 'timestamp' column as datetime: {e}")

    # Numeric checks
    numeric_cols = ["lat", "lon", "temp_c", "humidity_pct", "wind_speed_ms", "solar_radiation_wm2"]
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df_ordered[col]):
            try:
                df_ordered[col] = pd.to_numeric(df_ordered[col])
            except Exception as e:
                raise ValueError(f"Column '{col}' must be numeric: {e}")

    # Source check
    valid_sources = {s.value for s in WeatherSource}
    invalid_sources = set(df_ordered["source"].dropna().unique()) - valid_sources
    if invalid_sources:
        raise ValueError(
            f"Invalid weather source(s) found in DataFrame: {invalid_sources}. "
            f"Must be one of {valid_sources}"
        )

    return df_ordered


# ==============================================================================
# 2. Thermal Stress Index Schemas (Day 2 Scope)
# ==============================================================================

class HeatStressCategory(str, Enum):
    """Categorization of heat hazard severity."""
    NORMAL = "Normal"
    CAUTION = "Caution"
    EXTREME_CAUTION = "Extreme Caution"
    DANGER = "Danger"
    EXTREME_DANGER = "Extreme Danger"


class ThermalIndicesRecord(BaseModel):
    """Combined thermal stress indices for a single timestamp/location."""

    timestamp: datetime
    lat: float
    lon: float
    temp_c: float
    humidity_pct: float
    heat_index_c: float = Field(..., description="NOAA / Steadman Heat Index in Celsius")
    wbgt_c: float = Field(..., description="Wet Bulb Globe Temperature in Celsius")
    utci_c: float = Field(..., description="Universal Thermal Climate Index in Celsius")
    stress_category: HeatStressCategory = Field(..., description="Hazard severity level")


# ==============================================================================
# 3. Demographic & Environmental Vulnerability Schemas (Day 3 Scope)
# ==============================================================================

class VulnerabilityInput(BaseModel):
    """Raw demographic and socio-economic input features per ward (Census/PLFS)."""

    ward_id: str = Field(..., description="Unique municipal ward code e.g. AMD_01")
    ward_name: str = Field(..., description="Municipal ward name")
    elderly_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of population aged 60+")
    outdoor_worker_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage engaged in outdoor informal labor")
    slum_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage living in informal/slum settlements")
    green_cover_pct: float = Field(..., ge=0.0, le=100.0, description="Urban green canopy / vegetative cover %")
    hospital_bed_density: float = Field(..., ge=0.0, description="Hospital beds per 1,000 residents")


class VulnerabilityScore(BaseModel):
    """Calculated Heat Vulnerability Index (HVI) output with risk classification."""

    ward_id: str
    ward_name: str
    vulnerability_score: float = Field(..., ge=0.0, le=1.0, description="Composite Heat Vulnerability Index (0.0 to 1.0)")
    risk_tier: str = Field(..., description="Vulnerability classification tier: Low, Medium, High, Extreme")
    sub_indices: Dict[str, float] = Field(default_factory=dict, description="Breakdown of normalized individual factors")


class VulnerabilityMetrics(BaseModel):
    """Socio-demographic and environmental vulnerability indicators for a ward."""

    ward_id: str
    ward_name: str
    elderly_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of population aged > 60")
    children_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of population aged < 5")
    outdoor_workers_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage engaged in outdoor informal labor")
    slum_density_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage living in informal settlements/slums")
    ndvi_green_cover: float = Field(..., ge=-1.0, le=1.0, description="Normalized Difference Vegetation Index (vegetation density)")
    hvi_score: float = Field(..., ge=0.0, le=1.0, description="Composite Heat Vulnerability Index (0.0=lowest, 1.0=highest)")


class WardVulnerability(BaseModel):
    """Socio-demographic vulnerability indicators and absolute population counts per ward."""

    ward_id: str = Field(..., description="Unique municipal ward code e.g. AMD_01")
    ward_name: str = Field(..., description="Municipal ward name")
    elderly_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of population aged 60+")
    outdoor_worker_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage engaged in outdoor informal labor")
    slum_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage living in informal/slum settlements")
    green_cover_pct: float = Field(..., ge=0.0, le=100.0, description="Urban green canopy / vegetative cover %")
    hospital_bed_density: float = Field(..., ge=0.0, description="Hospital beds per 1,000 residents")

    # Absolute population counts per demographic segment (additive fields)
    total_population: int = Field(default=100000, ge=0, description="Total resident population")
    count_age_0_5: int = Field(default=0, ge=0, description="Children aged 0-5 years")
    count_age_6_17: int = Field(default=0, ge=0, description="School-age children/youth aged 6-17 years")
    count_age_18_59: int = Field(default=0, ge=0, description="Working-age adults aged 18-59 years")
    count_age_60_plus: int = Field(default=0, ge=0, description="Senior citizens aged 60+ years")
    count_outdoor_labor: int = Field(default=0, ge=0, description="Informal/outdoor manual laborers")
    count_indoor_labor: int = Field(default=0, ge=0, description="Indoor/formal sector workers")
    count_slum_residents: int = Field(default=0, ge=0, description="Residents living in informal/slum dwellings")

    # Explicit named counts (Part A)
    age_0_5_count: int = Field(default=0, ge=0, description="Children aged 0-5 count")
    age_6_17_count: int = Field(default=0, ge=0, description="Children/youth aged 6-17 count")
    age_18_59_count: int = Field(default=0, ge=0, description="Working adults aged 18-59 count")
    age_60plus_count: int = Field(default=0, ge=0, description="Senior citizens aged 60+ count")
    outdoor_labor_count: int = Field(default=0, ge=0, description="Outdoor informal labor count")
    indoor_labor_count: int = Field(default=0, ge=0, description="Indoor formal labor count")
    non_working_count: int = Field(default=0, ge=0, description="Non-working dependents count")
    slum_housing_count: int = Field(default=0, ge=0, description="Slum/informal housing resident count")

    # Provenance and Data Quality Metadata (Part A)
    data_quality: Dict[str, str] = Field(
        default_factory=lambda: {
            "total_population": "measured",
            "age_0_5": "derived",
            "age_6_17": "derived",
            "age_18_59": "derived",
            "elderly": "derived",
            "outdoor_labor": "derived",
            "indoor_labor": "derived",
            "slum": "derived",
        },
        description="Data quality labeling: 'measured' vs 'derived' per demographic indicator",
    )
    data_source_url: str = Field(
        default="https://censusindia.gov.in / MoSPI Periodic Labour Force Survey (PLFS)",
        description="Traceable Census or municipal benchmark source URL",
    )
    data_pulled_at: str = Field(
        default="2026-09-10",
        description="Date string when demographic data was fetched or standardized",
    )

    # Optional HVI scores
    vulnerability_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Calculated HVI score")
    risk_tier: Optional[str] = Field(default=None, description="HVI tier: Low, Medium, High, Extreme")


class PopulationSegmentImpact(BaseModel):
    """Impact assessment for a specific population demographic cohort."""

    segment_id: str = Field(..., description="Machine identifier e.g. children_under_5")
    name: str = Field(..., description="Human-readable segment title")
    icon: Optional[str] = Field(default="👥", description="Icon or emoji representing cohort")
    estimated_count: int = Field(..., ge=0, description="Estimated absolute population count")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of total ward population")
    data_quality: str = Field(default="derived", description="'measured' or 'derived' data quality badge")
    consequence: str = Field(..., description="Specific epidemiological/physiological consequence text")
    action: str = Field(default="", description="Specific public health action (precaution or urgent)")
    severity: str = Field(..., description="Health risk severity level: LOW, MODERATE, HIGH, CRITICAL")


class PopulationImpactResponse(BaseModel):
    """Population-segmented health consequence response for a specific municipal ward."""

    ward_id: str = Field(..., description="Ward identifier")
    ward_name: str = Field(..., description="Ward name")
    total_population: int = Field(..., ge=0, description="Total ward resident population")
    risk_tier: str = Field(default="MODERATE", description="Current heatwave risk tier name")
    risk_level: RiskLevel = Field(..., description="Current heatwave risk tier of the ward")
    final_risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite risk score (0.0 to 1.0)")
    dominant_risk_factor: str = Field(default="", description="Primary demographic exposure factor driving ward vulnerability")
    data_source_url: str = Field(
        default="https://censusindia.gov.in / MoSPI Periodic Labour Force Survey (PLFS)",
        description="Official Census / survey source URL",
    )
    data_pulled_at: str = Field(default="2026-09-10", description="Date when data was loaded/updated")
    segments: Dict[str, PopulationSegmentImpact] = Field(..., description="Breakdown by demographic group")
    total_vulnerable_count: int = Field(..., ge=0, description="Combined count of severely vulnerable residents")
    summary: str = Field(..., description="Actionable civic summary of population-level impacts")




# ==============================================================================
# 4. Ward Risk Score & GIS Schemas (Day 4 & 5 Scope)
# ==============================================================================

class RiskLevel(str, Enum):
    """Synthesized actionable risk rating."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    EXTREME = "EXTREME"


class WardRiskScore(BaseModel):
    """Ward-level integrated heatwave risk score (Thermal Stress × Vulnerability)."""

    ward_id: str
    ward_name: str
    city: str
    timestamp: datetime
    thermal_hazard_score: float = Field(..., ge=0.0, le=1.0, description="Normalized thermal stress index (0-1)")
    vulnerability_score: float = Field(..., ge=0.0, le=1.0, description="Normalized HVI score (0-1)")
    final_risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite risk metric (0-1)")
    risk_level: RiskLevel = Field(..., description="Categorical risk tier")
    recommended_action: str = Field(..., description="Actionable advisory for civic authorities / public")
    forecasts: List[Dict[str, Any]] = Field(default_factory=list, description="Multi-day predicted risk projections")


class WardGeometry(BaseModel):
    """GIS boundary definition for a ward."""

    ward_id: str
    ward_name: str
    city: str
    center_lat: float
    center_lon: float
    geojson: Dict[str, Any] = Field(..., description="GeoJSON Feature or Geometry object")


# ==============================================================================
# 5. Alert Trigger Schemas (Day 7 Scope)
# ==============================================================================

class AlertChannel(str, Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    WEBHOOK = "webhook"


class AlertRequest(BaseModel):
    """Payload for triggering an early warning dispatch."""

    ward_id: str
    recipient_phone: str
    channel: AlertChannel = AlertChannel.SMS
    force: bool = Field(default=False, description="Bypass minimum threshold check for manual demo testing")


class AlertResponse(BaseModel):
    """Result of an alert dispatch."""

    success: bool
    message_id: Optional[str] = None
    ward_id: str
    recipient_phone: str
    channel: AlertChannel
    dispatched_at: datetime = Field(default_factory=datetime.utcnow)
    detail: str
    message_text: Optional[str] = Field(default=None, description="Actual health advisory text transmitted")
    delivery_mode: str = Field(default="simulated", description="'live' or 'simulated'")
    whatsapp_url: Optional[str] = Field(default=None, description="Direct WhatsApp Web click-to-send URL")
    sms_url: Optional[str] = Field(default=None, description="Direct SMS click-to-send URL")


# ==============================================================================
# 6. Heat Copilot Conversational Assistant Schemas (Day 12 Scope)
# ==============================================================================

class CopilotIntent(str, Enum):
    """Categorical user message intent for Heat Copilot."""
    PERSONAL_RISK_QUERY = "personal_risk_query"
    GENERAL_QUESTION = "general_question"
    DASHBOARD_HELP = "dashboard_help"


class CopilotChatRequest(BaseModel):
    """Payload for conversational queries to Heat Copilot."""

    message: str = Field(..., description="User chat query")
    ward_id: Optional[str] = Field(default=None, description="Optional municipal ward ID (e.g. 'AMD_01')")
    user_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional demographic or personal context e.g. {'age_group': 'elderly', 'activity': 'outdoor_labor'}"
    )


class CopilotChatResponse(BaseModel):
    """Structured response from Heat Copilot."""

    response_text: str = Field(..., description="Main conversational response text")
    intent: Optional[str] = Field(default=None, description="Classified query intent")
    risk_score: Optional[float] = Field(default=None, description="Calculated risk score if personal query (0.0 to 1.0)")
    risk_tier: Optional[str] = Field(default=None, description="Calculated risk tier (LOW, MODERATE, HIGH, VERY_HIGH, EXTREME)")
    recommendation: Optional[str] = Field(default=None, description="Action recommendation (e.g. Avoid, Caution, Safe)")
    suggested_better_time: Optional[str] = Field(default=None, description="Suggested safer time window if high risk")
    dominant_factor: Optional[str] = Field(default=None, description="Primary physiological or thermal driver of risk")
    requires_ward_selection: bool = Field(default=False, description="True if copilot needs user to pick or name a ward")

