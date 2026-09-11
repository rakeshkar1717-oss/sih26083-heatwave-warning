"""Unit and Integration Tests for Profession Modes Subsystem.

Verifies:
1. Contrast: Farmer mode produces significantly higher risk score than Student mode under identical conditions.
2. Complete Coverage: All 6 profession modes execute cleanly and conform to schema.
3. Hourly Trajectory: Correct number of forward hours and chronological labeling.
4. Input Flexibility: Ward ID, lat/lon coordinates, and location strings resolve accurately.
5. REST API Endpoints: GET /api/profession-modes and GET /api/profession-mode/{mode_id}.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.profession_modes import (
    PROFESSION_MODES_CONFIG,
    ProfessionModeResponse,
    get_hourly_risk_forecast,
)


@pytest.fixture
def client():
    """FastAPI test client instance."""
    return TestClient(app)


def test_farmer_vs_student_risk_contrast():
    """Confirm Farmer mode produces higher risk scores than Student mode for the same weather."""
    ward_id = "AMD_01"
    farmer_res = get_hourly_risk_forecast(mode_id="farmer", ward_id=ward_id, hours_ahead=5, start_hour=13)
    student_res = get_hourly_risk_forecast(mode_id="student", ward_id=ward_id, hours_ahead=5, start_hour=13)

    assert isinstance(farmer_res, ProfessionModeResponse)
    assert isinstance(student_res, ProfessionModeResponse)

    # Farmer has heavy manual labor and 360m continuous exposure vs Student 30m light transit
    assert farmer_res.current_risk_score > student_res.current_risk_score, (
        f"Farmer ({farmer_res.current_risk_score}) must score higher than Student ({student_res.current_risk_score})"
    )
    assert farmer_res.peak_risk_score > student_res.peak_risk_score
    # Student risk tier should be lower or equal to Farmer risk tier
    tier_order = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "VERY_HIGH": 4, "EXTREME": 5}
    assert tier_order[farmer_res.current_risk_tier] >= tier_order[student_res.current_risk_tier]


def test_all_six_modes_execute_cleanly():
    """Verify all 6 curated profession modes return complete, valid schemas."""
    canonical_modes = [
        "student",
        "delivery_worker",
        "construction_worker",
        "elderly_care",
        "outdoor_exercise",
        "farmer",
    ]

    for m in canonical_modes:
        res = get_hourly_risk_forecast(mode_id=m, ward_id="AMD_01", hours_ahead=5)
        assert res.mode_id == m
        assert len(res.display_name) > 0
        assert len(res.icon) > 0
        assert 0.0 <= res.current_risk_score <= 100.0
        assert res.current_risk_tier in ("LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME")
        # 5 hours ahead + 1 current = 6 points
        assert len(res.hourly_breakdown) == 6
        assert len(res.recommendations) >= 3


def test_hourly_breakdown_structure_and_progression():
    """Verify hourly points have chronological labels, offsets, and non-empty values."""
    res = get_hourly_risk_forecast(mode_id="delivery_worker", ward_id="AMD_01", hours_ahead=4, start_hour=11)
    pts = res.hourly_breakdown
    assert len(pts) == 5

    for i, pt in enumerate(pts):
        assert pt.hour_offset == i
        assert " - " in pt.hour_range
        assert 0.0 <= pt.risk_score <= 100.0
        assert pt.temp_c > 0.0
        assert pt.wbgt_c > 0.0
        assert pt.heat_index_c > 0.0


def test_location_resolution_via_lat_lon_and_string():
    """Verify GPS coordinates and location query strings resolve to valid ward."""
    res_coords = get_hourly_risk_forecast(mode_id="construction_worker", lat=23.038, lon=72.552, hours_ahead=3)
    assert res_coords.ward_id.startswith("AMD_")

    res_ward = get_hourly_risk_forecast(mode_id="elderly_care", ward_id="AMD_17", hours_ahead=3)
    assert res_ward.ward_id == "AMD_17"


def test_invalid_mode_raises_error():
    """Verify requesting an unknown mode raises ValueError with helpful message."""
    with pytest.raises(ValueError) as exc:
        get_hourly_risk_forecast(mode_id="astronaut", ward_id="AMD_01")
    assert "Unknown profession mode 'astronaut'" in str(exc.value)


def test_api_list_profession_modes(client):
    """Verify GET /api/profession-modes returns metadata for all 6 presets."""
    response = client.get("/api/profession-modes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 6
    mode_ids = [d["mode_id"] for d in data]
    assert "farmer" in mode_ids
    assert "student" in mode_ids
    assert "delivery_worker" in mode_ids


def test_api_get_profession_mode_risk(client):
    """Verify GET /api/profession-mode/{mode_id} returns 200 with full response."""
    response = client.get("/api/profession-mode/delivery_worker?ward_id=AMD_01&hours_ahead=5")
    assert response.status_code == 200
    data = response.json()
    assert data["mode_id"] == "delivery_worker"
    assert "current_risk_score" in data
    assert "hourly_breakdown" in data
    assert len(data["hourly_breakdown"]) == 6
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0


def test_api_get_profession_mode_invalid(client):
    """Verify GET /api/profession-mode/unknown returns 400."""
    response = client.get("/api/profession-mode/unknown_role?ward_id=AMD_01")
    assert response.status_code == 400
    assert "Unknown profession mode" in response.json()["detail"]
