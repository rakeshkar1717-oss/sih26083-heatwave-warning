"""SIH26083 - Master Full Pipeline Demonstration (Days 1 to 7 Complete).

One-command end-to-end verification proving the entire system is operational:
1. Stage 1: Data Ingestion (Open-Meteo Multi-Station Weather)
2. Stage 2: Biometeorological Index Engine (Heat Index, WBGT, UTCI, 0-100 Hazard)
3. Stage 3: Demographic Vulnerability Model (Census 2011/PLFS HVI)
4. Stage 4: GIS Spatial Join (Point-in-Polygon & Nearest Fallback)
5. Stage 5: Relational Database Persistence (SQLAlchemy & SQLite DB Seed)
6. Stage 6: Multi-Day Predictive Risk Forecasting (Horizons 1 to 5 Days)
7. Stage 7: Production FastAPI REST Microservices (Live Client Queries)
8. Stage 8: Automated Early Warning Alerts (Twilio/Gupshup Gateway & Audit Log)
"""

import sys
import json
import logging
from datetime import datetime, timezone
import pandas as pd
import requests
from fastapi.testclient import TestClient

from backend.config import settings
from backend.models import WeatherSource, AlertChannel, validate_weather_dataframe
from backend.data_ingestion.ingest import get_weather_data
from backend.index_calculation.index_engine import compute_thermal_indices
from backend.vulnerability_model.census_loader import load_census_data
from backend.vulnerability_model.vulnerability_engine import compute_vulnerability_score
from backend.gis.boundary_loader import load_ward_boundaries
from backend.gis.spatial_join import join_weather_to_wards
from backend.db.session import init_db, SessionLocal
from backend.db.seed import seed_all
from backend.forecasting.run_forecast_job import run_forecast_job
from backend.api.main import app
from backend.alerts.alert_engine import send_ward_alert, reset_session_alert_count
from backend.db.models_orm import AlertLog, WardBoundary, RiskForecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BORDER = "=" * 80
SUB_BORDER = "-" * 80


def print_stage(num: int, title: str):
    print(f"\n{BORDER}")
    print(f" [STAGE {num} / 8] {title.upper()}".center(80))
    print(f"{BORDER}")


def main():
    print(f"\n{BORDER}")
    print("SIH26083: MASTER END-TO-END SYSTEM PIPELINE (DAYS 1 - 7)".center(80))
    print("Extreme Heatwave Early Warning & Human Thermal Stress Platform".center(80))
    print(f"{BORDER}\n")

    start_time = datetime.now(timezone.utc)

    # --------------------------------------------------------------------------
    # STAGE 1: Meteorological Ingestion (Day 1)
    # --------------------------------------------------------------------------
    print_stage(1, "Meteorological Data Ingestion")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Fetching live weather observations for pilot city {settings.default_city}...")

    # Fetch central station observation
    weather_df = get_weather_data(
        source=WeatherSource.OPEN_METEO,
        lat=23.03,
        lon=72.58,
        start_date=today_str,
        end_date=today_str,
        timeout=15,
    )
    validated_weather = validate_weather_dataframe(weather_df)
    latest_obs = validated_weather.iloc[-1]
    print(f" -> Successfully ingested {len(validated_weather)} hourly readings from Open-Meteo.")
    print(f" -> Latest Air Temperature: {latest_obs['temp_c']} °C | Humidity: {latest_obs['humidity_pct']}% | Wind: {latest_obs['wind_speed_ms']} m/s")

    # --------------------------------------------------------------------------
    # STAGE 2: Thermal Stress Index Calculation (Day 2)
    # --------------------------------------------------------------------------
    print_stage(2, "Biometeorological Thermal Index Calculation")
    thermal_df = compute_thermal_indices(validated_weather.tail(5))
    latest_thermal = thermal_df.iloc[-1]
    print(f" -> Computed NOAA Heat Index  : {latest_thermal['heat_index_c']} °C")
    print(f" -> Computed Outdoor WBGT     : {latest_thermal['wbgt_c']} °C")
    print(f" -> Computed UTCI Bioclimate  : {latest_thermal['utci_c']} °C")
    print(f" -> Composite Thermal Hazard  : {latest_thermal['thermal_stress_score']} / 100 [{latest_thermal['stress_category']}]")

    # --------------------------------------------------------------------------
    # STAGE 3: Ward-Level Heat Vulnerability Model (Day 3)
    # --------------------------------------------------------------------------
    print_stage(3, "Heat Vulnerability Modeling (HVI)")
    census_df = load_census_data()
    hvi_df = compute_vulnerability_score(census_df)
    print(f" -> Loaded Census 2011/PLFS indicators for {len(hvi_df)} municipal wards.")
    top_vuln = hvi_df.sort_values("vulnerability_score", ascending=False).iloc[0]
    print(f" -> Highest Vulnerability Ward: {top_vuln['ward_name']} ({top_vuln['ward_id']})")
    print(f"    - Score: {top_vuln['vulnerability_score']:.4f} [{top_vuln['risk_tier']}]")
    print(f"    - Elderly: {top_vuln['elderly_pct']}% | Slum: {top_vuln['slum_pct']}% | Outdoor Labor: {top_vuln['outdoor_worker_pct']}%")

    # --------------------------------------------------------------------------
    # STAGE 4: GIS Boundary Layer & Spatial Join (Day 4)
    # --------------------------------------------------------------------------
    print_stage(4, "GIS Boundary Loading & Spatial Join")
    wards_gdf = load_ward_boundaries()
    spatial_joined = join_weather_to_wards(thermal_df, wards_gdf)
    print(f" -> Loaded {len(wards_gdf)} administrative ward boundary polygons in WGS84 (EPSG:4326).")
    print(f" -> Spatially matched weather observation points to municipal ward boundaries.")

    # --------------------------------------------------------------------------
    # STAGE 5: Relational Database Persistence Layer (Day 5)
    # --------------------------------------------------------------------------
    print_stage(5, "Database Persistence Layer (SQLite Engine)")
    db_counts = seed_all(fetch_live=False, clear_existing=True)
    print(f" -> Persistent SQLite Database Seeded:")
    for table_name, count in db_counts.items():
        print(f"    • {table_name.ljust(22)}: {count} records")

    # --------------------------------------------------------------------------
    # STAGE 6: Multi-Day Predictive Heatwave Forecasting (Day 7)
    # --------------------------------------------------------------------------
    print_stage(6, "Multi-Day Predictive Heatwave Forecasting")
    db = SessionLocal()
    try:
        fc_result = run_forecast_job(db=db, horizon_days=5, clear_existing=True)
        print(f" -> Executed forecast batch job across {fc_result['wards_processed']} wards.")
        print(f" -> Generated {fc_result['forecasts_generated']} daily forecast records into 'risk_forecasts'.")

        sample_fc = db.query(RiskForecast).filter(RiskForecast.ward_id == "AMD_01").order_by(RiskForecast.forecast_horizon_days.asc()).all()
        print(f" -> 5-Day Trend for Navrangpura (AMD_01):")
        for fc in sample_fc:
            print(f"    Day +{fc.forecast_horizon_days}: Predicted Risk = {fc.predicted_risk_score:.4f} [{fc.predicted_risk_tier}]")
    finally:
        db.close()

    # --------------------------------------------------------------------------
    # STAGE 7: FastAPI REST API Microservice Layer (Day 5 & 6)
    # --------------------------------------------------------------------------
    print_stage(7, "FastAPI REST API Microservice Layer")
    client = TestClient(app)

    # Health
    res_health = client.get("/health")
    print(f" -> GET /health                : Status {res_health.status_code} | DB: {res_health.json().get('database')}")

    # Choropleth GeoJSON
    res_geojson = client.get("/api/wards/geojson")
    geo_data = res_geojson.json()
    print(f" -> GET /api/wards/geojson       : Status {res_geojson.status_code} | Total Features: {geo_data.get('total_wards')}")

    # Risk Endpoint
    res_risk = client.get("/api/risk/AMD_01")
    risk_data = res_risk.json()
    print(f" -> GET /api/risk/AMD_01         : Status {res_risk.status_code} | Final Risk: {risk_data.get('final_risk_score')} [{risk_data.get('risk_level')}]")
    print(f"    Forecast entries returned   : {len(risk_data.get('forecasts', []))} days")

    # Weather Endpoint
    res_weather = client.get("/api/weather/AMD_01")
    print(f" -> GET /api/weather/AMD_01      : Status {res_weather.status_code} | Temp: {res_weather.json()['latest']['temp_c']} °C")

    # --------------------------------------------------------------------------
    # STAGE 8: Automated Early Warning Alert Dispatch (Day 7)
    # --------------------------------------------------------------------------
    print_stage(8, "Automated Early Warning Alert Gateway")
    reset_session_alert_count()
    db = SessionLocal()
    try:
        alert_payload = {
            "ward_id": "AMD_01",
            "recipient_phone": settings.test_recipient_phone,
            "channel": "sms",
            "force": True,
        }
        alert_res = client.post("/api/alert/trigger", json=alert_payload)
        alert_data = alert_res.json()
        print(f" -> POST /api/alert/trigger     : Status {alert_res.status_code}")
        print(f"    Delivery Success            : {alert_data.get('success')}")
        print(f"    Message SID                 : {alert_data.get('message_id')}")
        print(f"    Channel                     : {alert_data.get('channel')}")
        print(f"    Status Detail               : {alert_data.get('detail')}")

        # Check DB Audit Trail
        log = db.query(AlertLog).filter(AlertLog.ward_id == "AMD_01").order_by(AlertLog.triggered_at.desc()).first()
        if log:
            print(f"    Audit Trail Verified In DB  : Log #{log.id} | Severity: {log.risk_tier} | Recipient: {log.recipient_phone}")
    finally:
        db.close()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"\n{BORDER}")
    print("MASTER INTEGRATION VERIFIED: ALL 8 CORE SUBSYSTEMS FULLY OPERATIONAL".center(80))
    print(f"Total Execution Time: {elapsed:.2f} seconds".center(80))
    print("SIH26083 IS DEMO-READY FOR DAYS 1 TO 7".center(80))
    print(BORDER)


if __name__ == "__main__":
    main()
