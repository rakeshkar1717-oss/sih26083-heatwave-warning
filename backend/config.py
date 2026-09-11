"""Central configuration for SIH26083 Extreme Heatwave Early Warning System.

All environment secrets are loaded dynamically from .env or environment variables.
Never hardcode API keys or credentials.
"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DATA_DIR = DATA_DIR / "cache"


class TargetCityConfig:
    """Target city coordinate metadata."""
    def __init__(self, name: str, state: str, lat: float, lon: float, total_wards: int = 48):
        self.name = name
        self.state = state
        self.lat = lat
        self.lon = lon
        self.total_wards = total_wards


# Pre-configured high-heat-risk pilot cities for SIH demonstration
TARGET_CITIES: Dict[str, TargetCityConfig] = {
    "Ahmedabad": TargetCityConfig(name="Ahmedabad", state="Gujarat", lat=23.0225, lon=72.5714, total_wards=48),
    "Nagpur": TargetCityConfig(name="Nagpur", state="Maharashtra", lat=21.1458, lon=79.0882, total_wards=38),
    "Delhi": TargetCityConfig(name="Delhi", state="Delhi", lat=28.6139, lon=77.2090, total_wards=272),
    "Hyderabad": TargetCityConfig(name="Hyderabad", state="Telangana", lat=17.3850, lon=78.4867, total_wards=150),
}

# Heat Stress Classification Thresholds (NOAA / NDMA Heat Index in Celsius)
HEAT_INDEX_THRESHOLDS = {
    "NORMAL": {"min": -100.0, "max": 27.0, "severity": 0, "color": "#2ecc71", "advisory": "Normal conditions"},
    "CAUTION": {"min": 27.0, "max": 32.0, "severity": 1, "color": "#f1c40f", "advisory": "Fatigue possible with prolonged exposure"},
    "EXTREME_CAUTION": {"min": 32.0, "max": 41.0, "severity": 2, "color": "#e67e22", "advisory": "Sunstroke, muscle cramps, and heat exhaustion possible"},
    "DANGER": {"min": 41.0, "max": 54.0, "severity": 3, "color": "#e74c3c", "advisory": "Sunstroke and heat exhaustion likely, heatstroke possible"},
    "EXTREME_DANGER": {"min": 54.0, "max": 100.0, "severity": 4, "color": "#8e44ad", "advisory": "Heatstroke highly imminent"},
}

# WBGT Occupational Heat Thresholds (ISO 7243 in Celsius)
WBGT_THRESHOLDS = {
    "LOW": {"max": 28.0, "work_rest_ratio": "Continuous work"},
    "MODERATE": {"min": 28.0, "max": 30.0, "work_rest_ratio": "75% work, 25% rest each hour"},
    "HIGH": {"min": 30.0, "max": 32.0, "work_rest_ratio": "50% work, 50% rest each hour"},
    "VERY_HIGH": {"min": 32.0, "max": 100.0, "work_rest_ratio": "25% work, 75% rest or cease outdoor labor"},
}

# Thermal Stress Index Composite Weights (Day 2)
# 40% WBGT (occupational/solar safety), 35% Heat Index (general sensation), 25% UTCI (dynamic biometeorology)
THERMAL_STRESS_WEIGHTS = {
    "heat_index": 0.35,
    "wbgt": 0.40,
    "utci": 0.25,
}

# Heat Vulnerability Index (HVI) Weights (Day 3)
# NOTE: These weights reflect baseline vulnerability indicators identified in the Ahmedabad Heat Action Plan (HAP)
# and can be recalibrated directly here based on published epidemiological excess-mortality regressions.
VULNERABILITY_WEIGHTS = {
    "elderly": 0.25,          # Population aged 60+ (higher physiological fragility)
    "outdoor_worker": 0.25,   # Informal street vendors, construction, delivery labor
    "slum": 0.20,             # Tin/asbestos roof dwellings & urban heat island density
    "green_cover": 0.15,      # Lack of urban tree canopy / cooling vegetative buffer (inverse)
    "hospital_bed": 0.15,     # Emergency medical infrastructure access (inverse)
}

# HVI Categorical Risk Tiers
VULNERABILITY_TIERS = {
    "Low": {"min": 0.0, "max": 0.30, "color": "#2ecc71"},
    "Medium": {"min": 0.30, "max": 0.50, "color": "#f1c40f"},
    "High": {"min": 0.50, "max": 0.75, "color": "#e67e22"},
    "Extreme": {"min": 0.75, "max": 1.00, "color": "#e74c3c"},
}

# Standard Integrated Risk Tier Thresholds (0.0 to 1.0 Composite Score)
# Default baseline boundaries
DEFAULT_RISK_TIER_THRESHOLDS: Dict[str, float] = {
    "LOW": 0.25,
    "MODERATE": 0.50,
    "HIGH": 0.70,
    "VERY_HIGH": 0.85,
}

# Empirically Tuned Risk Tier Thresholds (Stage 3 Optimization)
# Fine-tuned on multi-year multi-source fused ground truth to eliminate boundary misclassification
TUNED_RISK_TIER_THRESHOLDS: Dict[str, float] = {
    "LOW": 0.25,
    "MODERATE": 0.48,
    "HIGH": 0.68,
    "VERY_HIGH": 0.82,
}


# Flexible Column Aliases for Census/PLFS CSV Loaders (Day 3)
CENSUS_COLUMN_ALIASES = {
    "ward_id": ["ward_id", "ward_no", "ward_code", "ward_number", "wardid", "ward"],
    "ward_name": ["ward_name", "wardname", "name", "ward_title"],
    "elderly_pct": ["elderly_pct", "elderly_percentage", "pop_60_plus_pct", "senior_citizen_pct", "elderly_ratio", "elderly_pop_pct"],
    "outdoor_worker_pct": ["outdoor_worker_pct", "outdoor_workers_pct", "informal_workers_pct", "street_vendors_pct", "outdoor_pct"],
    "slum_pct": ["slum_pct", "slum_population_pct", "slum_density_pct", "informal_settlement_pct", "slum_ratio", "slum_households_pct"],
    "green_cover_pct": ["green_cover_pct", "ndvi_green_cover", "tree_canopy_pct", "vegetation_pct", "green_pct", "tree_cover_pct"],
    "hospital_bed_density": ["hospital_bed_density", "hospital_beds_per_1000", "bed_density", "health_infra", "beds_per_1k"],
    "total_population": ["total_population", "population", "tot_pop", "total_pop", "persons", "residents"],
    "count_age_0_5": ["count_age_0_5", "age_0_5_count", "pop_0_5", "children_under_5", "children_0_5", "age_0_5"],
    "count_age_6_17": ["count_age_6_17", "age_6_17_count", "pop_6_17", "youth_6_17", "school_age", "age_6_17"],
    "count_age_18_59": ["count_age_18_59", "age_18_59_count", "pop_18_59", "adults_18_59", "working_age", "age_18_59"],
    "count_age_60_plus": ["count_age_60_plus", "age_60plus_count", "age_60_plus_count", "pop_60_plus", "seniors_count", "elderly_count", "age_60_plus"],
    "count_outdoor_labor": ["count_outdoor_labor", "outdoor_labor_count", "outdoor_workers_count", "informal_labor_count", "outdoor_labor"],
    "count_indoor_labor": ["count_indoor_labor", "indoor_labor_count", "indoor_workers_count", "formal_labor_count", "indoor_labor"],
    "count_slum_residents": ["count_slum_residents", "slum_housing_count", "slum_population_count", "informal_housing_count", "slum_residents"],
    "non_working_count": ["non_working_count", "non_workers", "dependent_count"],
}

# Official City Population Benchmark (Ahmedabad Municipal Corporation Census 2011)
OFFICIAL_CITY_POPULATION_BENCHMARK: int = 5577940

# Official Census & Survey Data Provenance
DEFAULT_CENSUS_DATA_SOURCE_URL: str = (
    "https://censusindia.gov.in / MoSPI Periodic Labour Force Survey (PLFS)"
)


# Flexible Column Aliases for GeoJSON / Shapefile Boundaries (Day 4)
BOUNDARY_COLUMN_ALIASES = {
    "ward_id": ["ward_id", "ward_no", "ward_code", "ward_number", "id", "wardid", "admin_code"],
    "ward_name": ["ward_name", "wardname", "name", "ward_title", "admin_name", "zone_ward"],
}


# Default Raw Data Paths (Real & Synthetic)
CENSUS_REAL_PATH = RAW_DATA_DIR / "census_wards.csv"
CENSUS_SYNTHETIC_PATH = RAW_DATA_DIR / "synthetic_census_ahmedabad.csv"
BOUNDARY_REAL_PATH = RAW_DATA_DIR / "city_wards.geojson"
BOUNDARY_SYNTHETIC_PATH = RAW_DATA_DIR / "synthetic_ahmedabad_wards.geojson"
HISTORICAL_CACHE_PATH = CACHE_DATA_DIR / "historical_ahmedabad_may2010.csv"

# ==============================================================================
# HISTORICAL BACKTESTING CONFIGURATION (Day 8 Validation)
# ==============================================================================
# Target Event: Ahmedabad May 2010 Severe Heatwave (Catalyst for South Asia's 1st Heat Action Plan)
# Published Impact Citation:
#   Azhar GS, et al. (2014) Heat-Related Mortality in India: Excess All-Cause Mortality
#   Associated with the 2010 Ahmedabad Heat Wave. PLOS ONE 9(3): e91773.
#   Recorded peak temperature 46.8°C on May 21, 2010; 1,344 excess deaths (43% increase).
BACKTEST_EVENT = {
    "event_name": "Ahmedabad May 2010 Severe Heatwave",
    "city": "Ahmedabad",
    "state": "Gujarat",
    "lat": 23.03,
    "lon": 72.58,
    "start_date": "2010-05-15",
    "end_date": "2010-05-27",
    "peak_date": "2010-05-21",
    "peak_temp_c": 46.8,
    "published_excess_mortality": 1344,
    "mortality_increase_pct": 43.1,
    "source_citation": "Azhar GS, et al. (2014) Heat-Related Mortality in India: Excess All-Cause Mortality Associated with the 2010 Ahmedabad Heat Wave. PLOS ONE 9(3): e91773. doi:10.1371/journal.pone.0091773",
    "hap_reference": "Ahmedabad Municipal Corporation (AMC), NRDC, & IIPH-G Heat Action Plan (2013)",
}


class Settings(BaseSettings):
    """Central application settings validated via Pydantic."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database Persistence (SQLite local default, PostgreSQL/PostGIS compatible)
    database_url: str = Field(
        default=f"sqlite:///{PROCESSED_DATA_DIR / 'heatwave_sih.db'}",
        alias="DATABASE_URL"
    )

    # Data Mode: False uses real census/geojson in /data/raw/; True uses synthetic test fixtures
    use_synthetic_data: bool = Field(default=False, alias="USE_SYNTHETIC_DATA")

    # Copernicus Climate Data Store (ERA5)
    cds_api_url: str = Field(default="https://cds.climate.copernicus.eu/api", alias="CDS_API_URL")
    cds_api_key: Optional[str] = Field(default=None, alias="CDS_API_KEY")

    # Twilio Alert Gateway (Day 7)
    twilio_account_sid: Optional[str] = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, alias="TWILIO_PHONE_NUMBER")
    twilio_whatsapp_from: Optional[str] = Field(default="whatsapp:+14155238886", alias="TWILIO_WHATSAPP_FROM")

    # Gupshup Messaging (Day 7)
    gupshup_api_key: Optional[str] = Field(default=None, alias="GUPSHUP_API_KEY")
    gupshup_src_name: Optional[str] = Field(default=None, alias="GUPSHUP_SRC_NAME")
    gupshup_app_name: Optional[str] = Field(default=None, alias="GUPSHUP_APP_NAME")

    # Alert Thresholds & Safety Limits
    max_alerts_per_demo_run: int = Field(default=5, alias="MAX_ALERTS_PER_DEMO_RUN")
    alert_risk_threshold: str = Field(default="Extreme", alias="ALERT_RISK_THRESHOLD")
    test_recipient_phone: str = Field(default="+919876543210", alias="TEST_RECIPIENT_PHONE")
    max_subscription_attempts_per_hour: int = Field(default=3, alias="MAX_SUBSCRIPTION_ATTEMPTS_PER_HOUR")
    max_alerts_per_subscriber_per_day: int = Field(default=3, alias="MAX_ALERTS_PER_SUBSCRIBER_PER_DAY")

    # Application Defaults
    default_city: str = Field(default="Ahmedabad", alias="DEFAULT_CITY")
    default_lat: float = Field(default=23.03, alias="DEFAULT_LAT")
    default_lon: float = Field(default=72.58, alias="DEFAULT_LON")
    data_cache_dir: str = Field(default=str(CACHE_DATA_DIR), alias="DATA_CACHE_DIR")
    risk_tier_thresholds: Dict[str, float] = Field(
        default_factory=lambda: DEFAULT_RISK_TIER_THRESHOLDS.copy(),
        alias="RISK_TIER_THRESHOLDS"
    )

    # Historical Backtesting Settings (Day 8)
    backtest_start_date: str = Field(default="2010-05-15", alias="BACKTEST_START_DATE")
    backtest_end_date: str = Field(default="2010-05-27", alias="BACKTEST_END_DATE")

    # Server Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False


# Global singleton settings instance
settings = Settings()
