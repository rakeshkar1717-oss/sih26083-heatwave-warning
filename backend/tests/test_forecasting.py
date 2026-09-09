"""Unit tests for Multi-Day Predictive Heatwave Forecasting Module.

Tests horizon date sequences, risk synthesis formulas, tier classification,
and batch job execution using isolated in-memory SQLite fixtures without external network calls.
"""

from datetime import datetime, timezone, timedelta
import json
import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.session import init_db
from backend.db.models_orm import WardBoundary, WardVulnerability, RiskForecast
from backend.forecasting.forecast_engine import generate_forecast
from backend.forecasting.run_forecast_job import run_forecast_job


@pytest.fixture
def mock_forecast_weather_df():
    """Create 5 days of hourly weather fixture data."""
    records = []
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for d in range(1, 6):
        day_date = base + timedelta(days=d)
        for h in [6, 10, 14, 18, 22]:
            records.append({
                "timestamp": day_date + timedelta(hours=h),
                "lat": 23.03,
                "lon": 72.58,
                "temp_c": 38.0 + (d * 0.5),
                "humidity_pct": 45.0,
                "wind_speed_ms": 3.0,
                "solar_radiation_wm2": 750.0 if 10 <= h <= 14 else 100.0,
                "source": "open_meteo",
            })
    return pd.DataFrame(records)


@pytest.fixture
def in_memory_db():
    """Isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    # Add sample ward
    ward = WardBoundary(
        ward_id="AMD_TEST",
        ward_name="Test Forecast Ward",
        geometry_geojson=json.dumps({"type": "Point", "coordinates": [72.58, 23.03]}),
        city="Ahmedabad",
        center_lat=23.03,
        center_lon=72.58,
    )
    session.add(ward)

    vuln = WardVulnerability(
        ward_id="AMD_TEST",
        elderly_pct=15.0,
        outdoor_worker_pct=30.0,
        slum_pct=25.0,
        green_cover_pct=10.0,
        hospital_bed_density=2.0,
        vulnerability_score=0.65,
        risk_tier="High",
    )
    session.add(vuln)
    session.commit()

    yield session
    session.close()
    engine.dispose()


def test_generate_forecast_with_mock_weather(mock_forecast_weather_df):
    """Ensure generate_forecast computes 5-day projections accurately with mock weather."""
    forecasts = generate_forecast(
        ward_id="AMD_01",
        horizon_days=5,
        vuln_score=0.60,
        weather_df=mock_forecast_weather_df,
    )

    assert len(forecasts) == 5
    for i, fc in enumerate(forecasts, start=1):
        assert fc["horizon_days"] == i
        assert 0.0 <= fc["predicted_risk_score"] <= 1.0
        assert fc["predicted_risk_tier"] in ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
        assert "temp_max_c" in fc
        assert "wbgt_max_c" in fc
        assert fc["forecast_date"] > datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)


def test_generate_forecast_with_db_resolution(in_memory_db, mock_forecast_weather_df):
    """Ensure generate_forecast retrieves ward attributes and vulnerability from DB."""
    forecasts = generate_forecast(
        ward_id="AMD_TEST",
        horizon_days=3,
        db=in_memory_db,
        weather_df=mock_forecast_weather_df,
    )

    assert len(forecasts) == 3
    # Ward HVI was 0.65, so predicted risk should reflect high baseline
    assert forecasts[0]["predicted_risk_score"] > 0.40


def test_run_forecast_job_in_memory(in_memory_db):
    """Ensure run_forecast_job loops over database wards and populates RiskForecast table."""
    result = run_forecast_job(db=in_memory_db, horizon_days=5, clear_existing=True)
    assert result["wards_processed"] == 1
    assert result["forecasts_generated"] == 5

    stored = in_memory_db.query(RiskForecast).filter_by(ward_id="AMD_TEST").all()
    assert len(stored) == 5
    horizons = [s.forecast_horizon_days for s in stored]
    assert sorted(horizons) == [1, 2, 3, 4, 5]
