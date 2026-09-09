"""Unit tests for SIH26083 Database Models and Session Management.

Uses in-memory SQLite (sqlite:///:memory:) for fast, isolated, zero-footprint testing.
"""

from datetime import datetime, timezone
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models_orm import (
    Base,
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    RiskForecast,
    AlertLog,
)
from backend.db.session import init_db
from backend.db.seed import seed_all


@pytest.fixture
def in_memory_session():
    """Fixture providing an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    init_db(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_models_table_creation(in_memory_session):
    """Ensure all required tables are properly created."""
    engine = in_memory_session.get_bind()
    table_names = engine.dialect.get_table_names(engine.connect())
    expected = {
        "ward_boundaries",
        "ward_vulnerabilities",
        "weather_readings",
        "risk_forecasts",
        "alert_logs",
    }
    assert expected.issubset(set(table_names))


def test_ward_boundary_crud(in_memory_session):
    """Test creating, reading, and querying WardBoundary records."""
    dummy_geom = json.dumps({"type": "Polygon", "coordinates": [[[72.5, 23.0], [72.6, 23.0], [72.6, 23.1], [72.5, 23.1], [72.5, 23.0]]]})
    ward = WardBoundary(
        ward_id="TEST_01",
        ward_name="Test Ward",
        geometry_geojson=dummy_geom,
        city="Ahmedabad",
        zone="West",
        area_sqkm=5.2,
        center_lat=23.05,
        center_lon=72.55,
    )
    in_memory_session.add(ward)
    in_memory_session.commit()

    retrieved = in_memory_session.query(WardBoundary).filter_by(ward_id="TEST_01").first()
    assert retrieved is not None
    assert retrieved.ward_name == "Test Ward"
    assert retrieved.zone == "West"
    assert "Polygon" in retrieved.geometry_geojson
    assert "TEST_01" in repr(retrieved)


def test_ward_vulnerability_relationship(in_memory_session):
    """Test one-to-one relationship between WardBoundary and WardVulnerability."""
    dummy_geom = json.dumps({"type": "Point", "coordinates": [72.5, 23.0]})
    ward = WardBoundary(
        ward_id="TEST_02",
        ward_name="Vulnerability Test Ward",
        geometry_geojson=dummy_geom,
        city="Ahmedabad",
    )
    in_memory_session.add(ward)
    in_memory_session.commit()

    vuln = WardVulnerability(
        ward_id="TEST_02",
        elderly_pct=14.5,
        outdoor_worker_pct=28.0,
        slum_pct=35.0,
        green_cover_pct=8.5,
        hospital_bed_density=1.2,
        vulnerability_score=0.72,
        risk_tier="High",
        sub_indices_json=json.dumps({"elderly": 0.8}),
    )
    in_memory_session.add(vuln)
    in_memory_session.commit()

    retrieved_ward = in_memory_session.query(WardBoundary).filter_by(ward_id="TEST_02").first()
    assert retrieved_ward.vulnerability is not None
    assert retrieved_ward.vulnerability.vulnerability_score == 0.72
    assert retrieved_ward.vulnerability.risk_tier == "High"


def test_weather_reading_and_forecast_crud(in_memory_session):
    """Test WeatherReading and RiskForecast insertion and retrieval."""
    dummy_geom = json.dumps({"type": "Point", "coordinates": [72.5, 23.0]})
    ward = WardBoundary(
        ward_id="TEST_03",
        ward_name="Weather Test Ward",
        geometry_geojson=dummy_geom,
        city="Ahmedabad",
    )
    in_memory_session.add(ward)
    in_memory_session.commit()

    now = datetime.now(timezone.utc)
    reading = WeatherReading(
        ward_id="TEST_03",
        timestamp=now,
        temp_c=41.2,
        humidity_pct=38.0,
        wind_speed_ms=4.1,
        solar_radiation_wm2=850.0,
        source="open_meteo",
        heat_index_c=48.5,
        wbgt_c=31.2,
        utci_c=42.0,
        thermal_stress_score=82.5,
    )
    in_memory_session.add(reading)

    forecast = RiskForecast(
        ward_id="TEST_03",
        forecast_date=now,
        forecast_horizon_days=1,
        predicted_risk_score=0.78,
        predicted_risk_tier="HIGH",
        generated_at=now,
    )
    in_memory_session.add(forecast)
    in_memory_session.commit()

    retrieved_reading = in_memory_session.query(WeatherReading).filter_by(ward_id="TEST_03").first()
    assert retrieved_reading.temp_c == 41.2
    assert retrieved_reading.thermal_stress_score == 82.5

    retrieved_forecast = in_memory_session.query(RiskForecast).filter_by(ward_id="TEST_03").first()
    assert retrieved_forecast.predicted_risk_score == 0.78
    assert retrieved_forecast.predicted_risk_tier == "HIGH"


def test_alert_log_crud(in_memory_session):
    """Test AlertLog persistence."""
    dummy_geom = json.dumps({"type": "Point", "coordinates": [72.5, 23.0]})
    ward = WardBoundary(
        ward_id="TEST_04",
        ward_name="Alert Ward",
        geometry_geojson=dummy_geom,
        city="Ahmedabad",
    )
    in_memory_session.add(ward)
    in_memory_session.commit()

    alert = AlertLog(
        ward_id="TEST_04",
        risk_tier="EXTREME",
        message_sent="Extreme heat warning for TEST_04",
        channel="sms",
        recipient_phone="+919876543210",
        recipient_count=1,
        success=True,
    )
    in_memory_session.add(alert)
    in_memory_session.commit()

    retrieved_alert = in_memory_session.query(AlertLog).filter_by(ward_id="TEST_04").first()
    assert retrieved_alert is not None
    assert retrieved_alert.channel == "sms"
    assert retrieved_alert.success is True
    assert "TEST_04" in repr(retrieved_alert)


def test_seed_pipeline_in_memory(in_memory_session):
    """Ensure seed_all executes cleanly on an in-memory session."""
    counts = seed_all(db=in_memory_session, fetch_live=False, clear_existing=True)
    assert counts["ward_boundaries"] == 48
    assert counts["ward_vulnerabilities"] == 48
    assert counts["weather_readings"] > 0
    assert counts["risk_forecasts"] > 0
