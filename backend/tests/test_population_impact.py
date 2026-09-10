"""Tests for Population Impact Breakdown and Epidemiological Health Consequence Mapping."""

import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.main import app
from backend.db.session import get_db, init_db
from backend.db.models_orm import (
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    RiskForecast,
)
from backend.vulnerability_model.health_consequence_map import (
    HEALTH_CONSEQUENCE_MAP,
    get_health_consequence,
    get_segment_severity,
    normalize_risk_level_key,
    get_population_impact,
    build_population_impact_breakdown,
)
from backend.vulnerability_model.census_loader import load_census_data


def test_population_math_consistency(tmp_path):
    """Verify that percentage × total = count for all cohorts."""
    csv_file = tmp_path / "test_pop_census.csv"
    total_pop = 150000
    elderly_pct = 12.0
    outdoor_pct = 25.0
    slum_pct = 30.0

    csv_file.write_text(
        f"ward_code,ward_title,total_population,elderly_pct,outdoor_worker_pct,slum_pct,green_pct,beds_per_1k\n"
        f"W_POP_01,Test Pop Ward,{total_pop},{elderly_pct},{outdoor_pct},{slum_pct},15.0,2.5\n"
    )

    df = load_census_data(csv_file)
    row = df.iloc[0]

    assert row["total_population"] == total_pop
    assert row["count_age_60_plus"] == int(round(total_pop * (elderly_pct / 100.0)))
    assert row["count_outdoor_labor"] == int(round(total_pop * (outdoor_pct / 100.0)))
    assert row["count_slum_residents"] == int(round(total_pop * (slum_pct / 100.0)))

    # Children age 0-5 benchmark 9.2%
    expected_children = int(round(total_pop * 0.092))
    assert row["count_age_0_5"] == expected_children

    # Youth age 6-17 benchmark 18.8%
    expected_youth = int(round(total_pop * 0.188))
    assert row["count_age_6_17"] == expected_youth

    # Working-age adults age 18-59
    assert row["count_age_18_59"] == total_pop - expected_children - expected_youth - row["count_age_60_plus"]


def test_consequence_text_progression_across_tiers():
    """Verify that clinical health consequence texts change distinctly across risk tiers."""
    segments = ["children_under_5", "elderly_60_plus", "outdoor_workers", "slum_residents"]

    for seg in segments:
        low_text = get_health_consequence(seg, "LOW")
        mod_text = get_health_consequence(seg, "MODERATE")
        high_text = get_health_consequence(seg, "HIGH")
        vhigh_text = get_health_consequence(seg, "VERY_HIGH")
        extreme_text = get_health_consequence(seg, "EXTREME")

        # Each tier must provide distinct clinical guidance
        assert low_text != high_text
        assert high_text != vhigh_text
        assert vhigh_text != extreme_text

        # Severity tags must elevate with hazard tiers
        assert get_segment_severity(seg, "LOW") in ("LOW", "MODERATE")
        assert get_segment_severity(seg, "VERY_HIGH") in ("VERY_HIGH", "CRITICAL")
        assert get_segment_severity(seg, "EXTREME") == "CRITICAL"


def test_scientific_citations_present():
    """Verify presence of WHO and NRDC Ahmedabad HAP references in epidemiological text."""
    # Outdoor workers & elderly should cite WHO or Ahmedabad HAP
    outdoor_vhigh = HEALTH_CONSEQUENCE_MAP["outdoor_workers"]["consequences"]["VERY_HIGH"]
    outdoor_extreme = HEALTH_CONSEQUENCE_MAP["outdoor_workers"]["consequences"]["EXTREME"]
    children_extreme = HEALTH_CONSEQUENCE_MAP["children_under_5"]["consequences"]["EXTREME"]
    elderly_extreme = HEALTH_CONSEQUENCE_MAP["elderly_60_plus"]["consequences"]["EXTREME"]
    slum_high = HEALTH_CONSEQUENCE_MAP["slum_residents"]["consequences"]["HIGH"]

    assert "Ahmedabad Heat Action Plan" in outdoor_vhigh
    assert "NRDC / AMC 2018" in outdoor_extreme
    assert "Azhar et al." in children_extreme or "PLOS ONE" in children_extreme
    assert "Ahmedabad HAP" in elderly_extreme
    assert "NRDC" in slum_high


def test_build_population_impact_breakdown():
    """Verify payload generation from synthesize function."""
    impact = build_population_impact_breakdown(
        ward_id="WARD_99",
        ward_name="Shahpur",
        total_population=85000,
        elderly_pct=15.0,
        outdoor_worker_pct=30.0,
        slum_pct=25.0,
        risk_level="VERY_HIGH",
        final_risk_score=0.88,
    )

    assert impact["ward_id"] == "WARD_99"
    assert impact["total_population"] == 85000
    assert impact["risk_level"] == "VERY_HIGH"
    assert "segments" in impact
    assert len(impact["segments"]) == 4

    elderly = impact["segments"].get("elderly_60plus") or impact["segments"].get("elderly_60_plus")
    assert elderly["estimated_count"] == int(round(85000 * 0.15))
    assert elderly["severity"] == "CRITICAL"
    assert "cardiovascular" in elderly["consequence"].lower() or "cerebrovascular" in elderly["consequence"].lower() or "heatstroke" in elderly["consequence"].lower()


@pytest.fixture(scope="module")
def api_test_client():
    """In-memory SQLite client for testing the REST endpoint."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()

    ward = WardBoundary(
        ward_id="AMD_TEST_POP",
        ward_name="Jamalpur",
        geometry_geojson=json.dumps({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}),
        city="Ahmedabad",
        zone="Central",
        area_sqkm=3.2,
        center_lat=23.01,
        center_lon=72.58,
    )
    session.add(ward)

    vuln = WardVulnerability(
        ward_id="AMD_TEST_POP",
        total_population=120000,
        elderly_pct=18.0,
        outdoor_worker_pct=35.0,
        slum_pct=40.0,
        green_cover_pct=5.0,
        hospital_bed_density=1.5,
        vulnerability_score=0.78,
        risk_tier="Very High",
        count_age_60_plus=21600,
        count_outdoor_labor=42000,
        count_slum_residents=48000,
        count_age_0_5=11040,
        count_age_6_17=22560,
        count_age_18_59=64800,
        count_indoor_labor=12000,
    )
    session.add(vuln)

    now = datetime.now(timezone.utc)
    weather = WeatherReading(
        ward_id="AMD_TEST_POP",
        timestamp=now,
        temp_c=43.0,
        humidity_pct=40.0,
        wind_speed_ms=2.0,
        solar_radiation_wm2=800.0,
        source="open_meteo",
        heat_index_c=48.0,
        wbgt_c=33.0,
        utci_c=44.0,
        thermal_stress_score=85.0,
    )
    session.add(weather)

    forecast = RiskForecast(
        ward_id="AMD_TEST_POP",
        forecast_date=now,
        forecast_horizon_days=1,
        predicted_risk_score=0.82,
        predicted_risk_tier="Very High",
    )
    session.add(forecast)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_precaution_vs_urgent_action_switching():
    """Verify that consequences and prevention actions switch between precaution and urgent across tiers."""
    ward_dummy = {
        "ward_id": "TEST_WARD",
        "ward_name": "Test Ward",
        "total_population": 100000,
        "elderly_pct": 15.0,
        "outdoor_worker_pct": 30.0,
        "slum_pct": 25.0,
    }

    # Moderate tier: precaution actions and risk labels
    mod_impact = get_population_impact(ward_dummy, risk_tier="MODERATE")
    for seg_key in ["children_0_5", "elderly_60plus", "outdoor_workers", "slum_residents"]:
        seg = mod_impact["segments"][seg_key]
        assert seg["action"] != ""
        assert "MANDATORY" not in seg["action"]
        assert "EMERGENCY" not in seg["action"]
        assert seg["data_quality"] in ("derived", "measured")

    # Extreme tier: urgent actions and extreme risk labels
    ext_impact = get_population_impact(ward_dummy, risk_tier="EXTREME")
    for seg_key in ["children_0_5", "elderly_60plus", "outdoor_workers", "slum_residents"]:
        seg = ext_impact["segments"][seg_key]
        assert seg["action"] != ""
        # Actions must be urgent at extreme hazard
        assert seg["severity"] == "CRITICAL"
        assert seg["consequence"] != mod_impact["segments"][seg_key]["consequence"]
        assert seg["action"] != mod_impact["segments"][seg_key]["action"]

    # Dominant factor check: outdoor (30.0%) vs slum (25.0%) vs elderly (15.0%)
    assert "Outdoor labor exposure (30.0%)" in ext_impact["dominant_risk_factor"]


def test_api_population_impact_endpoint(api_test_client):
    """Test GET /api/population-impact/{ward_id} returns 200 and expected schema."""
    resp = api_test_client.get("/api/population-impact/AMD_TEST_POP")
    assert resp.status_code == 200
    data = resp.json()

    assert data["ward_id"] == "AMD_TEST_POP"
    assert data["ward_name"] == "Jamalpur"
    assert data["total_population"] == 120000
    assert data["risk_level"] in ("VERY_HIGH", "Very High")
    assert "dominant_risk_factor" in data
    assert "data_source_url" in data
    assert "data_pulled_at" in data
    assert "segments" in data

    elderly = data["segments"]["elderly_60plus"]
    assert elderly["estimated_count"] == int(round(120000 * 0.18))
    assert elderly["percentage"] == 18.0
    assert len(elderly["consequence"]) > 20
    assert len(elderly["action"]) > 10
    assert elderly["severity"] == "CRITICAL"


def test_api_population_impact_not_found(api_test_client):
    """Test GET /api/population-impact/{ward_id} for nonexistent ward returns 404."""
    resp = api_test_client.get("/api/population-impact/NONEXISTENT_WARD_XYZ")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

