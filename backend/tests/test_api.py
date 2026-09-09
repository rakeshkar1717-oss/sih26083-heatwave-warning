"""Integration and Contract Tests for FastAPI Backend Endpoints.

Uses FastAPI TestClient with dependency override against an in-memory SQLite
database to test live queries, schemas, error codes, and business logic.
"""

from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.main import app
from backend.db.session import get_db, init_db
from backend.db.models_orm import (
    Base,
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    RiskForecast,
    AlertLog,
)


@pytest.fixture(scope="module")
def test_db_engine():
    """Create isolated in-memory SQLite engine for API testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()

    # Seed sample ward data
    geom_json = json.dumps({
        "type": "Polygon",
        "coordinates": [[[72.55, 23.03], [72.57, 23.03], [72.57, 23.05], [72.55, 23.05], [72.55, 23.03]]]
    })

    ward = WardBoundary(
        ward_id="AMD_01",
        ward_name="Navrangpura",
        geometry_geojson=geom_json,
        city="Ahmedabad",
        zone="West",
        area_sqkm=4.85,
        center_lat=23.04,
        center_lon=72.56,
    )
    session.add(ward)

    vuln = WardVulnerability(
        ward_id="AMD_01",
        elderly_pct=14.2,
        outdoor_worker_pct=26.5,
        slum_pct=22.0,
        green_cover_pct=12.0,
        hospital_bed_density=3.5,
        vulnerability_score=0.62,
        risk_tier="High",
        sub_indices_json=json.dumps({"elderly": 0.65}),
    )
    session.add(vuln)

    now = datetime.now(timezone.utc)
    weather = WeatherReading(
        ward_id="AMD_01",
        timestamp=now,
        temp_c=42.5,
        humidity_pct=36.0,
        wind_speed_ms=3.8,
        solar_radiation_wm2=820.0,
        source="open_meteo",
        heat_index_c=47.2,
        wbgt_c=32.1,
        utci_c=43.5,
        thermal_stress_score=84.5,
    )
    session.add(weather)

    forecast = RiskForecast(
        ward_id="AMD_01",
        forecast_date=now,
        forecast_horizon_days=1,
        predicted_risk_score=0.76,
        predicted_risk_tier="HIGH",
        generated_at=now,
    )
    session.add(forecast)

    session.commit()
    session.close()

    yield engine
    engine.dispose()


@pytest.fixture
def client(test_db_engine):
    """Provide TestClient with database dependency overridden to test_db_engine."""
    TestingSession = sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    """Ensure root metadata is returned with valid endpoint list."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "SIH26083" in data["project"]
    assert data["target_city"] == "Ahmedabad"
    assert "/api/wards/geojson" in data["endpoints"]


def test_health_endpoint(client):
    """Ensure health endpoint reports connected database and ward count."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["wards_count"] >= 1


def test_wards_geojson_endpoint(client):
    """Ensure GeoJSON FeatureCollection serves valid GeoJSON with required risk attributes."""
    response = client.get("/api/wards/geojson")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["total_wards"] >= 1
    feature = data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["id"] == "AMD_01"
    assert "geometry" in feature
    assert feature["geometry"]["type"] == "Polygon"

    props = feature["properties"]
    assert props["ward_id"] == "AMD_01"
    assert props["ward_name"] == "Navrangpura"
    assert "final_risk_score" in props
    assert "risk_level" in props
    assert "color" in props
    assert props["color"].startswith("#")
    assert props["temp_c"] == 42.5
    assert props["vulnerability_score"] == 0.62


def test_risk_endpoint_success(client):
    """Ensure /api/risk/{ward_id} conforms to WardRiskScore schema."""
    response = client.get("/api/risk/AMD_01")
    assert response.status_code == 200
    data = response.json()
    assert data["ward_id"] == "AMD_01"
    assert data["city"] == "Ahmedabad"
    assert 0.0 <= data["thermal_hazard_score"] <= 1.0
    assert 0.0 <= data["vulnerability_score"] <= 1.0
    assert 0.0 <= data["final_risk_score"] <= 1.0
    assert data["risk_level"] in ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
    assert len(data["recommended_action"]) > 10


def test_risk_endpoint_not_found(client):
    """Ensure /api/risk with invalid ward_id returns 404."""
    response = client.get("/api/risk/NON_EXISTENT_WARD")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_weather_endpoint_success(client):
    """Ensure /api/weather/{ward_id} returns latest reading and history."""
    response = client.get("/api/weather/AMD_01")
    assert response.status_code == 200
    data = response.json()
    assert data["ward_id"] == "AMD_01"
    assert data["latest"]["temp_c"] == 42.5
    assert data["latest"]["source"] == "open_meteo"
    assert len(data["history"]) >= 1


def test_weather_endpoint_not_found(client):
    """Ensure /api/weather with invalid ward_id returns 404."""
    response = client.get("/api/weather/UNKNOWN_WARD")
    assert response.status_code == 404


def test_forecast_endpoint(client):
    """Ensure /api/forecast/{ward_id} returns multi-day projections."""
    response = client.get("/api/forecast/AMD_01")
    assert response.status_code == 200
    data = response.json()
    assert data["ward_id"] == "AMD_01"
    assert len(data["forecasts"]) >= 1
    assert data["forecasts"][0]["horizon_days"] == 1


def test_alert_trigger_forced(client):
    """Ensure forced alert dispatches and persists to database."""
    payload = {
        "ward_id": "AMD_01",
        "recipient_phone": "+919876543210",
        "channel": "sms",
        "force": True,
    }
    response = client.post("/api/alert/trigger", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message_id"].startswith(("MSG-", "SM", "WA", "GS"))
    assert data["channel"] == "sms"


def test_alert_trigger_invalid_ward(client):
    """Ensure triggering alert on non-existent ward returns 404."""
    payload = {
        "ward_id": "INVALID_WARD_99",
        "recipient_phone": "+919876543210",
        "channel": "sms",
        "force": True,
    }
    response = client.post("/api/alert/trigger", json=payload)
    assert response.status_code == 404
