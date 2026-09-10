"""Database Seeding Pipeline for SIH26083 Extreme Heatwave Early Warning System.

Populates relational database with:
1. Municipal Ward Boundaries (GeoJSON / Spatial)
2. Socio-demographic Heat Vulnerability Index (HVI)
3. Spatially interpolated weather observations and calculated thermal indices
4. Multi-day risk forecasts per ward
"""

import json
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from backend.config import (
    settings,
    CENSUS_REAL_PATH,
    CENSUS_SYNTHETIC_PATH,
    BOUNDARY_REAL_PATH,
    BOUNDARY_SYNTHETIC_PATH,
)
from backend.db.session import engine, SessionLocal, init_db
from backend.db.models_orm import (
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    RiskForecast,
    AlertLog,
)
from backend.gis.boundary_loader import load_ward_boundaries
from backend.vulnerability_model.census_loader import load_census_data
from backend.vulnerability_model.vulnerability_engine import compute_vulnerability_score
from backend.index_calculation.index_engine import compute_thermal_indices
from backend.data_ingestion.ingest import get_weather_data
from backend.models import WeatherSource, RiskLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _classify_risk_tier_from_score(score: float) -> str:
    """Classify 0.0 - 1.0 composite risk score into standard risk tier."""
    if score < 0.25:
        return RiskLevel.LOW.value
    elif score < 0.50:
        return RiskLevel.MODERATE.value
    elif score < 0.70:
        return RiskLevel.HIGH.value
    elif score < 0.85:
        return RiskLevel.VERY_HIGH.value
    else:
        return RiskLevel.EXTREME.value


def seed_boundaries(db: Session, geojson_path: Optional[str] = None) -> gpd.GeoDataFrame:
    """Load spatial ward boundaries and populate WardBoundary table."""
    wards_gdf = load_ward_boundaries(geojson_path)
    logger.info("Seeding %d ward boundary polygons...", len(wards_gdf))

    for _, row in wards_gdf.iterrows():
        ward_id = str(row["ward_id"])
        ward_name = str(row["ward_name"])
        geom = row["geometry"]
        geojson_str = json.dumps(mapping(geom))

        # Centroid coordinates
        centroid = geom.centroid
        center_lat = float(centroid.y)
        center_lon = float(centroid.x)

        # Approximate area in sq km if not provided
        area_sqkm = float(row.get("area_sqkm", 0.0))
        if area_sqkm <= 0.0 and geom.is_valid:
            # Rough geographic approximation in Gujarat (~111 km/deg lat, ~102 km/deg lon)
            area_sqkm = round(geom.area * 111.0 * 102.0, 3)

        zone = str(row.get("zone", "AMC Zone"))

        boundary_obj = WardBoundary(
            ward_id=ward_id,
            ward_name=ward_name,
            geometry_geojson=geojson_str,
            city=settings.default_city,
            zone=zone,
            area_sqkm=area_sqkm,
            center_lat=center_lat,
            center_lon=center_lon,
        )
        db.merge(boundary_obj)

    db.flush()
    logger.info("Successfully seeded ward boundaries.")
    return wards_gdf


def seed_vulnerabilities(db: Session, csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load demographic indicators, calculate HVI, and populate WardVulnerability table."""
    census_df = load_census_data(csv_path)
    hvi_df = compute_vulnerability_score(census_df)
    logger.info("Seeding %d ward vulnerability scores...", len(hvi_df))

    for _, row in hvi_df.iterrows():
        ward_id = str(row["ward_id"])

        # Sub-indices breakdown for transparency
        sub_indices = {
            "elderly": float(row.get("norm_elderly", 0.5)),
            "outdoor_worker": float(row.get("norm_outdoor", 0.5)),
            "slum": float(row.get("norm_slum", 0.5)),
            "green_cover": float(row.get("norm_inv_green", 0.5)),
            "hospital_bed": float(row.get("norm_inv_beds", 0.5)),
        }

        vuln_obj = WardVulnerability(
            ward_id=ward_id,
            elderly_pct=float(row["elderly_pct"]),
            outdoor_worker_pct=float(row["outdoor_worker_pct"]),
            slum_pct=float(row["slum_pct"]),
            green_cover_pct=float(row["green_cover_pct"]),
            hospital_bed_density=float(row["hospital_bed_density"]),
            total_population=int(row.get("total_population", 100000)),
            count_age_0_5=int(row.get("count_age_0_5", 0)),
            count_age_6_17=int(row.get("count_age_6_17", 0)),
            count_age_18_59=int(row.get("count_age_18_59", 0)),
            count_age_60_plus=int(row.get("count_age_60_plus", 0)),
            count_outdoor_labor=int(row.get("count_outdoor_labor", 0)),
            count_indoor_labor=int(row.get("count_indoor_labor", 0)),
            count_slum_residents=int(row.get("count_slum_residents", 0)),
            vulnerability_score=round(float(row["vulnerability_score"]), 4),
            risk_tier=str(row["risk_tier"]),
            sub_indices_json=json.dumps(sub_indices),
            last_updated=datetime.now(timezone.utc),
        )
        db.merge(vuln_obj)

    db.flush()
    logger.info("Successfully seeded ward vulnerabilities.")
    return hvi_df


def _generate_synthetic_weather(wards_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Generate realistic high-temperature synthetic weather observations for Ahmedabad."""
    now_utc = datetime.now(timezone.utc)
    records = []

    for _, row in wards_gdf.iterrows():
        centroid = row["geometry"].centroid
        lat, lon = centroid.y, centroid.x
        ward_id = str(row["ward_id"])

        # Generate last 24 hours of hourly readings
        for hour_offset in range(24, -1, -3):
            obs_time = now_utc - timedelta(hours=hour_offset)
            # Diurnal temperature cycle peaking in afternoon
            hour_val = (obs_time.hour + 5) % 24  # Local IST offset rough estimate
            diurnal_factor = np.sin((hour_val - 8) * np.pi / 16) if 8 <= hour_val <= 20 else -0.3
            temp_c = round(34.0 + 8.5 * max(0.0, diurnal_factor) + np.random.uniform(-0.8, 0.8), 2)
            humidity_pct = round(52.0 - 20.0 * max(0.0, diurnal_factor) + np.random.uniform(-2.0, 2.0), 1)
            wind_speed_ms = round(3.5 + np.random.uniform(-1.0, 1.5), 2)
            solar_wm2 = round(max(0.0, 850.0 * diurnal_factor + np.random.uniform(-20.0, 20.0)), 1)

            records.append({
                "timestamp": obs_time,
                "lat": lat,
                "lon": lon,
                "temp_c": temp_c,
                "humidity_pct": max(15.0, min(95.0, humidity_pct)),
                "wind_speed_ms": max(0.5, wind_speed_ms),
                "solar_radiation_wm2": solar_wm2,
                "source": "open_meteo",
                "ward_id": ward_id,
            })

    return pd.DataFrame(records)


def seed_weather_and_forecasts(
    db: Session,
    wards_gdf: gpd.GeoDataFrame,
    hvi_df: pd.DataFrame,
    fetch_live: bool = True
) -> int:
    """Ingest/synthesize weather readings, compute thermal indices, and generate risk forecasts."""
    logger.info("Generating weather readings and multi-day risk forecasts...")

    weather_df = None
    if fetch_live:
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            # Anchor weather station in central Ahmedabad
            live_df = get_weather_data(
                source=WeatherSource.OPEN_METEO,
                lat=23.03,
                lon=72.58,
                start_date=today_str,
                end_date=today_str,
                timeout=15,
            )
            if not live_df.empty:
                logger.info("Live weather ingested successfully from Open-Meteo.")
                # Distribute across wards with microclimate variation
                records = []
                now_utc = datetime.now(timezone.utc)
                latest = live_df.iloc[-1]
                for _, row in wards_gdf.iterrows():
                    centroid = row["geometry"].centroid
                    ward_id = str(row["ward_id"])
                    records.append({
                        "timestamp": now_utc,
                        "lat": centroid.y,
                        "lon": centroid.x,
                        "temp_c": float(latest["temp_c"]) + np.random.uniform(-0.5, 0.5),
                        "humidity_pct": float(latest["humidity_pct"]) + np.random.uniform(-1.5, 1.5),
                        "wind_speed_ms": float(latest["wind_speed_ms"]),
                        "solar_radiation_wm2": float(latest["solar_radiation_wm2"]),
                        "source": "open_meteo",
                        "ward_id": ward_id,
                    })
                weather_df = pd.DataFrame(records)
        except Exception as e:
            logger.warning("Live weather fetch encountered network exception (%s). Falling back to synthetic baseline.", e)

    if weather_df is None or weather_df.empty:
        weather_df = _generate_synthetic_weather(wards_gdf)

    # Calculate thermal indices
    thermal_df = compute_thermal_indices(weather_df)
    logger.info("Seeding %d weather readings with thermal indices...", len(thermal_df))

    for _, row in thermal_df.iterrows():
        reading = WeatherReading(
            ward_id=str(row["ward_id"]),
            timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
            temp_c=float(row["temp_c"]),
            humidity_pct=float(row["humidity_pct"]),
            wind_speed_ms=float(row["wind_speed_ms"]),
            solar_radiation_wm2=float(row["solar_radiation_wm2"]),
            source=str(row["source"]),
            heat_index_c=round(float(row["heat_index_c"]), 2),
            wbgt_c=round(float(row["wbgt_c"]), 2),
            utci_c=round(float(row["utci_c"]), 2),
            thermal_stress_score=round(float(row["thermal_stress_score"]), 2),
        )
        db.add(reading)

    # Multi-day risk forecasts (Horizons 1 to 5 days)
    hvi_map = {str(r["ward_id"]): float(r["vulnerability_score"]) for _, r in hvi_df.iterrows()}
    # Get latest reading per ward for baseline hazard
    latest_readings = thermal_df.sort_values("timestamp").groupby("ward_id").last().reset_index()

    now_utc = datetime.now(timezone.utc)
    forecast_count = 0
    for _, row in latest_readings.iterrows():
        ward_id = str(row["ward_id"])
        base_hazard = float(row["thermal_stress_score"]) / 100.0
        vuln_score = hvi_map.get(ward_id, 0.5)

        for horizon in range(1, 6):
            # Model progressive temperature elevation over 5 days
            horizon_hazard = min(1.0, max(0.0, base_hazard + (horizon - 1) * 0.03 + np.random.uniform(-0.02, 0.03)))
            predicted_risk = round(0.60 * horizon_hazard + 0.40 * vuln_score, 4)
            tier = _classify_risk_tier_from_score(predicted_risk)

            forecast = RiskForecast(
                ward_id=ward_id,
                forecast_date=now_utc + timedelta(days=horizon),
                forecast_horizon_days=horizon,
                predicted_risk_score=predicted_risk,
                predicted_risk_tier=tier,
                generated_at=now_utc,
            )
            db.add(forecast)
            forecast_count += 1

    db.flush()
    logger.info("Successfully seeded %d risk forecast records.", forecast_count)
    return len(thermal_df)


def seed_all(
    db: Optional[Session] = None,
    fetch_live: bool = False,
    clear_existing: bool = True
) -> Dict[str, int]:
    """Execute complete end-to-end database initialization and seeding pipeline."""
    init_db()
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        if clear_existing:
            logger.info("Clearing existing records for fresh seed...")
            db.query(AlertLog).delete()
            db.query(RiskForecast).delete()
            db.query(WeatherReading).delete()
            db.query(WardVulnerability).delete()
            db.query(WardBoundary).delete()
            db.commit()

        wards_gdf = seed_boundaries(db)
        hvi_df = seed_vulnerabilities(db)
        weather_count = seed_weather_and_forecasts(db, wards_gdf, hvi_df, fetch_live=fetch_live)
        db.commit()

        counts = {
            "ward_boundaries": db.query(WardBoundary).count(),
            "ward_vulnerabilities": db.query(WardVulnerability).count(),
            "weather_readings": db.query(WeatherReading).count(),
            "risk_forecasts": db.query(RiskForecast).count(),
            "alert_logs": db.query(AlertLog).count(),
        }
        logger.info("Database seeding completed successfully! Summary: %s", counts)
        return counts

    except Exception as e:
        db.rollback()
        logger.error("Database seeding failed: %s", e, exc_info=True)
        raise
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed SIH26083 database.")
    parser.add_argument("--live", action="store_true", help="Attempt live weather ingestion from Open-Meteo")
    parser.add_argument("--keep-existing", action="store_true", help="Do not clear existing database tables")
    args = parser.parse_args()

    seed_all(fetch_live=args.live, clear_existing=not args.keep_existing)
