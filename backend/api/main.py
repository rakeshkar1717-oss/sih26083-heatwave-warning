"""FastAPI Application for SIH26083 Extreme Heatwave Early Warning System.

Exposes production-ready REST endpoints for:
- /api/weather/{ward_id} : Weather observations and forecasts per ward
- /api/risk/{ward_id}    : Synthesized risk scores and advisories per ward
- /api/wards/geojson     : GeoJSON ward boundaries with real-time risk choropleth properties
- /api/forecast/{ward_id}: Multi-day predicted heatwave risk timeline
- /api/alert/trigger     : Automated early warning dispatch via SMS / WhatsApp / Webhook
- /health                : Service and database health check
"""

import json
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
import pandas as pd

from backend.config import settings
from backend.db.session import get_db, init_db
from backend.db.models_orm import (
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    RiskForecast,
    AlertLog,
)
from backend.models import (
    AlertRequest,
    AlertResponse,
    AlertChannel,
    RiskLevel,
    WardRiskScore,
)
from backend.alerts.alert_engine import send_ward_alert

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema is initialized and auto-seeded on application startup."""
    try:
        init_db()
        from backend.db.session import SessionLocal
        from backend.db.seed import seed_all
        db = SessionLocal()
        try:
            if db.query(WardBoundary).count() == 0:
                logger.info("Database is empty on cold start. Auto-seeding pilot city data...")
                seed_all(db)
                logger.info("Auto-seeding complete.")
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not auto-initialize DB on startup: %s", e)
    yield


app = FastAPI(
    title="SIH26083: Heatwave Early Warning & Thermal Stress API",
    description=(
        "Production backend microservices delivering high-resolution municipal ward-level "
        "human thermal stress calculations, socio-demographic vulnerability indices, "
        "multi-day predictive risk forecasts, and automated early warning alert logging."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Leaflet.js frontend dashboard and civic portals
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _compute_risk_level(composite_score: float) -> RiskLevel:
    """Determine categorical risk rating from 0.0 - 1.0 composite score."""
    if composite_score < 0.25:
        return RiskLevel.LOW
    elif composite_score < 0.50:
        return RiskLevel.MODERATE
    elif composite_score < 0.70:
        return RiskLevel.HIGH
    elif composite_score < 0.85:
        return RiskLevel.VERY_HIGH
    else:
        return RiskLevel.EXTREME


def _get_advisory_text(risk_level: RiskLevel, ward_name: str) -> str:
    """Generate actionable municipal and public advisories tailored to risk severity."""
    advisories = {
        RiskLevel.EXTREME: (
            f"CRITICAL HEAT EMERGENCY for {ward_name}: Cease all outdoor physical labor immediately. "
            "Municipal authorities must activate maximum cooling shelters, mobilize mobile hydration tankers, "
            "and place emergency hospital heatstroke units on Code Red alert."
        ),
        RiskLevel.VERY_HIGH: (
            f"SEVERE HEAT ALERT for {ward_name}: Mandatory cessation of strenuous outdoor physical work "
            "between 11:00 AM and 4:30 PM. Distribute oral rehydration salts (ORS) across informal settlements "
            "and high-density transit corridors."
        ),
        RiskLevel.HIGH: (
            f"HIGH HEAT ADVISORY for {ward_name}: Restrict outdoor manual labor between 12:00 PM and 4:00 PM. "
            "Activate municipal drinking water kiosks, ensure shaded resting zones, and alert vulnerable elderly residents."
        ),
        RiskLevel.MODERATE: (
            f"MODERATE HEAT CAUTION for {ward_name}: Recommend frequent hydration and periodic shaded rest "
            "for outdoor workers and school children. Monitor vulnerable demographics."
        ),
        RiskLevel.LOW: (
            f"NORMAL CONDITIONS for {ward_name}: Normal civic and economic operations. "
            "Maintain baseline municipal heat action plan monitoring."
        ),
    }
    return advisories.get(risk_level, advisories[RiskLevel.MODERATE])


def _get_risk_color(risk_level: RiskLevel) -> str:
    """Hex color code for choropleth rendering."""
    colors = {
        RiskLevel.LOW: "#2ecc71",        # Green
        RiskLevel.MODERATE: "#f1c40f",   # Yellow
        RiskLevel.HIGH: "#e67e22",       # Orange
        RiskLevel.VERY_HIGH: "#e74c3c",  # Red
        RiskLevel.EXTREME: "#8e44ad",    # Purple
    }
    return colors.get(risk_level, "#3498db")


@app.get("/")
def root() -> Dict[str, Any]:
    """Root metadata and API discovery endpoint."""
    return {
        "project": "SIH26083: Extreme Heatwave Early Warning & Human Thermal Stress Index",
        "version": "1.0.0",
        "status": "operational",
        "target_city": settings.default_city,
        "endpoints": [
            "/api/wards/geojson",
            "/api/india/geojson",
            "/api/risk/{ward_id}",
            "/api/weather/{ward_id}",
            "/api/forecast/{ward_id}",
            "/api/alert/trigger",
            "/api/backtest/summary",
            "/api/backtest/timeline",
            "/api/backtest/geojson",
            "/health",
            "/docs",
        ],
    }


@app.get("/health")
def health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Service health check and database connectivity validation."""
    db_status = "connected"
    wards_count = 0
    try:
        wards_count = db.query(WardBoundary).count()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "wards_count": wards_count,
    }


@app.get("/api/wards/geojson")
def get_wards_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve GeoJSON FeatureCollection of municipal ward boundaries with live risk properties.

    Optimized for Leaflet.js choropleth rendering, popup tooltips, and interactive filtering.
    """
    wards = db.query(WardBoundary).all()
    if not wards:
        logger.info("WardBoundary table is empty. Running automatic seed fallback...")
        try:
            from backend.db.seed import seed_all
            seed_all(db)
            wards = db.query(WardBoundary).all()
        except Exception as seed_err:
            logger.error("Auto-seed fallback failed: %s", seed_err)

    if not wards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ward boundaries found in database. Please run db seed pipeline.",
        )

    features = []
    for ward in wards:
        vuln = ward.vulnerability
        # Latest weather reading for this ward
        latest_weather = (
            db.query(WeatherReading)
            .filter(WeatherReading.ward_id == ward.ward_id)
            .order_by(desc(WeatherReading.timestamp))
            .first()
        )

        hazard_score = (latest_weather.thermal_stress_score / 100.0) if latest_weather else 0.65
        vuln_score = vuln.vulnerability_score if vuln else 0.50
        final_risk = round(0.60 * hazard_score + 0.40 * vuln_score, 4)
        risk_tier = _compute_risk_level(final_risk)

        try:
            geometry_dict = json.loads(ward.geometry_geojson)
        except Exception:
            geometry_dict = {"type": "Polygon", "coordinates": []}

        properties = {
            "ward_id": ward.ward_id,
            "ward_name": ward.ward_name,
            "city": ward.city,
            "zone": ward.zone or "Unassigned",
            "area_sqkm": ward.area_sqkm,
            "center_lat": ward.center_lat,
            "center_lon": ward.center_lon,
            # Vulnerability
            "vulnerability_score": vuln_score,
            "vulnerability_tier": vuln.risk_tier if vuln else "Medium",
            "elderly_pct": vuln.elderly_pct if vuln else None,
            "outdoor_worker_pct": vuln.outdoor_worker_pct if vuln else None,
            "slum_pct": vuln.slum_pct if vuln else None,
            "green_cover_pct": vuln.green_cover_pct if vuln else None,
            "hospital_bed_density": vuln.hospital_bed_density if vuln else None,
            # Thermal / Weather
            "temp_c": latest_weather.temp_c if latest_weather else None,
            "humidity_pct": latest_weather.humidity_pct if latest_weather else None,
            "heat_index_c": latest_weather.heat_index_c if latest_weather else None,
            "wbgt_c": latest_weather.wbgt_c if latest_weather else None,
            "utci_c": latest_weather.utci_c if latest_weather else None,
            "thermal_stress_score": latest_weather.thermal_stress_score if latest_weather else None,
            # Synthesized Risk
            "thermal_hazard_score": round(hazard_score, 4),
            "final_risk_score": final_risk,
            "risk_level": risk_tier.value,
            "color": _get_risk_color(risk_tier),
            "advisory": _get_advisory_text(risk_tier, ward.ward_name),
        }

        features.append({
            "type": "Feature",
            "id": ward.ward_id,
            "geometry": geometry_dict,
            "properties": properties,
        })

    return {
        "type": "FeatureCollection",
        "city": settings.default_city,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_wards": len(features),
        "features": features,
    }


_INDIA_GEOJSON_CACHE: Optional[Dict[str, Any]] = None


@app.get("/api/india/geojson")
def get_india_geojson() -> Dict[str, Any]:
    """Retrieve GeoJSON FeatureCollection of all Indian States and Union Territories.

    Contains regional biometeorological hazard metrics, WBGT, Heat Index, and HVI demographic vulnerability.
    """
    global _INDIA_GEOJSON_CACHE
    if _INDIA_GEOJSON_CACHE is not None:
        return _INDIA_GEOJSON_CACHE

    from backend.config import RAW_DATA_DIR, BASE_DIR
    india_geojson_path = RAW_DATA_DIR / "india_states.geojson"
    if not india_geojson_path.exists():
        india_geojson_path = BASE_DIR / "data" / "raw" / "india_states.geojson"

    if not india_geojson_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="India regional GeoJSON dataset not found. Please verify data/raw/india_states.geojson.",
        )

    with open(india_geojson_path, "r", encoding="utf-8") as f:
        _INDIA_GEOJSON_CACHE = json.load(f)

    return _INDIA_GEOJSON_CACHE


@app.get("/api/risk/{ward_id}", response_model=WardRiskScore)
def get_ward_risk(ward_id: str, db: Session = Depends(get_db)) -> WardRiskScore:
    """Retrieve composite heatwave risk score and civic advisory for a specific ward."""
    ward = db.query(WardBoundary).filter(WardBoundary.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward '{ward_id}' not found in database.",
        )

    vuln = ward.vulnerability
    latest_weather = (
        db.query(WeatherReading)
        .filter(WeatherReading.ward_id == ward.ward_id)
        .order_by(desc(WeatherReading.timestamp))
        .first()
    )

    hazard_score = (latest_weather.thermal_stress_score / 100.0) if latest_weather else 0.65
    vuln_score = vuln.vulnerability_score if vuln else 0.50
    final_risk = round(0.60 * hazard_score + 0.40 * vuln_score, 4)
    risk_tier = _compute_risk_level(final_risk)

    forecast_records = (
        db.query(RiskForecast)
        .filter(RiskForecast.ward_id == ward.ward_id)
        .order_by(RiskForecast.forecast_horizon_days.asc())
        .all()
    )
    forecast_list = [
        {
            "horizon_days": fc.forecast_horizon_days,
            "forecast_date": fc.forecast_date.isoformat(),
            "predicted_risk_score": fc.predicted_risk_score,
            "predicted_risk_tier": fc.predicted_risk_tier,
        }
        for fc in forecast_records
    ]

    return WardRiskScore(
        ward_id=ward.ward_id,
        ward_name=ward.ward_name,
        city=ward.city,
        timestamp=latest_weather.timestamp if latest_weather else datetime.now(timezone.utc),
        thermal_hazard_score=round(hazard_score, 4),
        vulnerability_score=round(vuln_score, 4),
        final_risk_score=final_risk,
        risk_level=risk_tier,
        recommended_action=_get_advisory_text(risk_tier, ward.ward_name),
        forecasts=forecast_list,
    )


@app.get("/api/weather/{ward_id}")
def get_ward_weather(ward_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve meteorological observations, thermal indices, and history for a specific ward."""
    ward = db.query(WardBoundary).filter(WardBoundary.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward '{ward_id}' not found in database.",
        )

    readings = (
        db.query(WeatherReading)
        .filter(WeatherReading.ward_id == ward.ward_id)
        .order_by(desc(WeatherReading.timestamp))
        .limit(24)
        .all()
    )

    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weather observations recorded for ward '{ward_id}'.",
        )

    latest = readings[0]
    history = [
        {
            "timestamp": r.timestamp.isoformat(),
            "temp_c": r.temp_c,
            "humidity_pct": r.humidity_pct,
            "wind_speed_ms": r.wind_speed_ms,
            "solar_radiation_wm2": r.solar_radiation_wm2,
            "heat_index_c": r.heat_index_c,
            "wbgt_c": r.wbgt_c,
            "utci_c": r.utci_c,
            "thermal_stress_score": r.thermal_stress_score,
            "source": r.source,
        }
        for r in readings
    ]

    return {
        "ward_id": ward.ward_id,
        "ward_name": ward.ward_name,
        "city": ward.city,
        "center_lat": ward.center_lat,
        "center_lon": ward.center_lon,
        "latest": history[0],
        "history_count": len(history),
        "history": history,
    }


@app.get("/api/forecast/{ward_id}")
def get_ward_forecast(ward_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve 5-day predictive heatwave risk projections for a specific ward."""
    ward = db.query(WardBoundary).filter(WardBoundary.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward '{ward_id}' not found in database.",
        )

    forecasts = (
        db.query(RiskForecast)
        .filter(RiskForecast.ward_id == ward.ward_id)
        .order_by(RiskForecast.forecast_horizon_days.asc())
        .all()
    )

    return {
        "ward_id": ward.ward_id,
        "ward_name": ward.ward_name,
        "city": ward.city,
        "forecasts": [
            {
                "horizon_days": f.forecast_horizon_days,
                "forecast_date": f.forecast_date.isoformat(),
                "predicted_risk_score": f.predicted_risk_score,
                "predicted_risk_tier": f.predicted_risk_tier,
                "generated_at": f.generated_at.isoformat(),
            }
            for f in forecasts
        ],
    }


@app.post("/api/alert/trigger", response_model=AlertResponse)
def trigger_alert(payload: AlertRequest, db: Session = Depends(get_db)) -> AlertResponse:
    """Trigger and log an early warning alert dispatch via SMS, WhatsApp, or Webhook."""
    ward = db.query(WardBoundary).filter(WardBoundary.ward_id == payload.ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot dispatch alert: Ward '{payload.ward_id}' does not exist.",
        )

    return send_ward_alert(
        ward_id=payload.ward_id,
        recipient_phone=payload.recipient_phone,
        channel=payload.channel,
        force=payload.force,
        db=db,
    )


# ==============================================================================
# Historical Backtesting & Validation Endpoints (Day 8 / Day 9 Live Demo)
# ==============================================================================

_backtest_cache: Optional[Dict[str, Any]] = None


def _get_backtest_data() -> Dict[str, Any]:
    """Retrieve and cache historical backtest analysis results in memory."""
    global _backtest_cache
    if _backtest_cache is None:
        from backend.backtesting.validation_report import run_backtest_pipeline
        _backtest_cache = run_backtest_pipeline()
    return _backtest_cache


@app.get("/api/backtest/summary")
def get_backtest_summary() -> Dict[str, Any]:
    """Retrieve historical heatwave backtest event metadata and validation findings."""
    data = _get_backtest_data()
    meta = data["event_metadata"]
    peak = data["peak_summary"]

    return {
        "event_name": meta["event_name"],
        "city": meta["city"],
        "state": meta["state"],
        "date_window": f"{meta['start_date']} to {meta['end_date']}",
        "peak_date": data["peak_date"],
        "peak_temp_c": peak["max_temp_c"],
        "peak_heat_index_c": peak["max_heat_index_c"],
        "peak_wbgt_c": peak["max_wbgt_c"],
        "peak_thermal_hazard": peak["max_thermal_stress"],
        "published_excess_mortality": meta["published_excess_mortality"],
        "mortality_increase_pct": meta["mortality_increase_pct"],
        "source_citation": meta["source_citation"],
        "hap_reference": meta["hap_reference"],
        "validation_status": "Empirically Validated against Azhar et al. (2014) PLOS ONE",
    }


@app.get("/api/backtest/timeline")
def get_backtest_timeline() -> Dict[str, Any]:
    """Retrieve day-by-day historical heatwave progression for timeline rendering."""
    data = _get_backtest_data()
    daily_records = data["daily_df"].to_dict(orient="records")
    return {
        "event": data["event_metadata"]["event_name"],
        "total_days": len(daily_records),
        "timeline": daily_records,
    }


@app.get("/api/backtest/geojson")
def get_backtest_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve GeoJSON FeatureCollection showing peak historical heatwave conditions (May 21, 2010).

    Enables 'Backtest Mode' on the Leaflet dashboard, instantly transforming the map to show
    how the system flagged the real historical catastrophe.
    """
    data = _get_backtest_data()
    ward_risk_df = data["ward_risk_df"].set_index("ward_id")
    peak = data["peak_summary"]

    wards = db.query(WardBoundary).all()
    if not wards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ward boundaries found in database.",
        )

    features = []
    for ward in wards:
        try:
            geometry_dict = json.loads(ward.geometry_geojson)
        except Exception:
            geometry_dict = {"type": "Polygon", "coordinates": []}

        # Look up historical risk for this ward
        if ward.ward_id in ward_risk_df.index:
            w_row = ward_risk_df.loc[ward.ward_id]
            vuln_score = float(w_row["vulnerability_score"])
            vuln_tier = str(w_row["vulnerability_tier"])
            final_risk = float(w_row["final_risk_score"])
            risk_tier = _compute_risk_level(final_risk)
            elderly = float(w_row["elderly_pct"]) if pd.notna(w_row["elderly_pct"]) else 8.0
            outdoor = float(w_row["outdoor_worker_pct"]) if pd.notna(w_row["outdoor_worker_pct"]) else 45.0
            slum = float(w_row["slum_pct"]) if pd.notna(w_row["slum_pct"]) else 35.0
            green = float(w_row["green_cover_pct"]) if pd.notna(w_row["green_cover_pct"]) else 12.0
        else:
            vuln_score = 0.50
            vuln_tier = "Medium"
            hazard = peak["max_thermal_stress"] / 100.0
            final_risk = round(0.60 * hazard + 0.40 * vuln_score, 4)
            risk_tier = _compute_risk_level(final_risk)
            elderly, outdoor, slum, green = 8.0, 45.0, 35.0, 12.0

        advisory = (
            f"HISTORICAL BACKTEST (May 21, 2010) for {ward.ward_name}: Observed peak 45.4°C (46.8°C stn), "
            f"Outdoor WBGT {peak['max_wbgt_c']}°C (mandatory work cessation breached). "
            f"Catastrophic heat conditions matching published 43% excess mortality surge (Azhar et al. 2014)."
        )

        properties = {
            "ward_id": ward.ward_id,
            "ward_name": ward.ward_name,
            "city": ward.city,
            "zone": ward.zone or "Unassigned",
            "area_sqkm": ward.area_sqkm,
            "center_lat": ward.center_lat,
            "center_lon": ward.center_lon,
            "vulnerability_score": vuln_score,
            "vulnerability_tier": vuln_tier,
            "elderly_pct": elderly,
            "outdoor_worker_pct": outdoor,
            "slum_pct": slum,
            "green_cover_pct": green,
            "temp_c": peak["max_temp_c"],
            "heat_index_c": peak["max_heat_index_c"],
            "wbgt_c": peak["max_wbgt_c"],
            "utci_c": peak["max_utci_c"],
            "thermal_stress_score": peak["max_thermal_stress"],
            "thermal_hazard_score": round(peak["max_thermal_stress"] / 100.0, 4),
            "final_risk_score": final_risk,
            "risk_level": risk_tier.value,
            "color": _get_risk_color(risk_tier),
            "advisory": advisory,
            "is_historical_backtest": True,
        }

        features.append({
            "type": "Feature",
            "id": ward.ward_id,
            "geometry": geometry_dict,
            "properties": properties,
        })

    return {
        "type": "FeatureCollection",
        "city": "Ahmedabad",
        "timestamp": "2010-05-21T14:00:00Z",
        "is_backtest_mode": True,
        "event": "Ahmedabad May 2010 Heatwave Peak",
        "total_wards": len(features),
        "features": features,
    }
