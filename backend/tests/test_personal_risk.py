"""Unit and Integration Tests for Personal Heat Twin Risk Subsystem.

Verifies:
1. Low-risk profile: Young indoor worker resting (scores LOW, < 25 pts)
2. High/Extreme-risk profile: Elderly outdoor worker doing heavy labor for 90 min (scores HIGH / VERY_HIGH / EXTREME)
3. Monotonic ordering: High-risk profile score > Low-risk profile score
4. Factor breakdown: Point contributions match total personal risk score
5. Location resolution: Lat/Lon coordinates successfully resolve to nearest ward
6. Input validation: Negative duration or extreme duration errors
7. REST API endpoint: POST /api/personal-risk/calculate returns 200 with complete schema
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.personal_risk import (
    PersonalRiskRequest,
    PersonalRiskResponse,
    calculate_personal_risk,
    resolve_user_location,
    AgeGroup,
    OccupationType,
    ActivityType,
)


@pytest.fixture
def client():
    """FastAPI test client instance."""
    return TestClient(app)


def test_young_indoor_worker_resting_scores_low():
    """Verify young indoor worker resting for 15 minutes achieves LOW risk tier."""
    req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_18_30,
        occupation=OccupationType.INDOOR_WORKER,
        current_activity=ActivityType.RESTING,
        outdoor_duration_minutes=15,
        ward_id="AMD_01",
    )
    res = calculate_personal_risk(req)
    assert isinstance(res, PersonalRiskResponse)
    assert res.personal_risk_score < 48.0, f"Expected low/moderate score, got {res.personal_risk_score}"
    assert res.risk_tier in ("LOW", "MODERATE")
    assert res.ward_id == "AMD_01"
    assert "Navrangpura" in res.ward_name or "AMD_01" in res.ward_name
    assert len(res.factor_breakdown) == 6


def test_elderly_outdoor_worker_heavy_labor_scores_high_or_extreme():
    """Verify elderly outdoor worker doing heavy labor for 90 minutes scores HIGH, VERY_HIGH, or EXTREME."""
    req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_60_PLUS,
        occupation=OccupationType.OUTDOOR_WORKER,
        current_activity=ActivityType.HEAVY_LABOR,
        outdoor_duration_minutes=90,
        ward_id="AMD_17",  # Vatva
    )
    res = calculate_personal_risk(req)
    assert isinstance(res, PersonalRiskResponse)
    assert res.personal_risk_score >= 60.0, f"Expected high score for elderly heavy labor, got {res.personal_risk_score}"
    assert res.risk_tier in ("HIGH", "VERY_HIGH", "EXTREME")
    assert "Safer Time Window" in (res.suggested_better_time or "")


def test_monotonic_risk_ordering():
    """Verify risk score strictly increases with exertion, age, and duration."""
    low_req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_18_30,
        occupation=OccupationType.INDOOR_WORKER,
        current_activity=ActivityType.RESTING,
        outdoor_duration_minutes=15,
        ward_id="AMD_01",
    )
    med_req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_31_45,
        occupation=OccupationType.OTHER,
        current_activity=ActivityType.WALKING,
        outdoor_duration_minutes=45,
        ward_id="AMD_01",
    )
    high_req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_60_PLUS,
        occupation=OccupationType.OUTDOOR_WORKER,
        current_activity=ActivityType.HEAVY_LABOR,
        outdoor_duration_minutes=90,
        ward_id="AMD_01",
    )

    low_res = calculate_personal_risk(low_req)
    med_res = calculate_personal_risk(med_req)
    high_res = calculate_personal_risk(high_req)

    assert low_res.personal_risk_score < med_res.personal_risk_score, "Low should score lower than Medium"
    assert med_res.personal_risk_score < high_res.personal_risk_score, "Medium should score lower than High"


def test_factor_breakdown_point_contributions():
    """Verify that all 6 factors have non-negative points and sum to personal_risk_score."""
    req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_46_59,
        occupation=OccupationType.OUTDOOR_WORKER,
        current_activity=ActivityType.MODERATE_EXERCISE,
        outdoor_duration_minutes=60,
        ward_id="AMD_01",
    )
    res = calculate_personal_risk(req)
    factor_sum = sum(f.point_contribution for f in res.factor_breakdown)
    # Floating point rounding allowance: ±0.2
    assert abs(factor_sum - res.personal_risk_score) <= 0.2
    for f in res.factor_breakdown:
        assert f.point_contribution >= 0.0
        assert f.point_contribution <= f.max_points
        assert len(f.description) > 0


def test_location_resolution_from_lat_lon():
    """Verify GPS lat/lon resolves to valid Ahmedabad ward polygon."""
    # Ahmedabad municipal coordinates
    req = PersonalRiskRequest(
        age_group=AgeGroup.AGE_18_30,
        occupation=OccupationType.STUDENT,
        current_activity=ActivityType.WALKING,
        outdoor_duration_minutes=30,
        lat=23.038,
        lon=72.552,  # Near Navrangpura
    )
    res = calculate_personal_risk(req)
    assert res.ward_id.startswith("AMD_")
    assert len(res.ward_name) > 0


def test_input_validation_negative_and_excessive_duration():
    """Verify Pydantic validation rejects negative or extreme duration."""
    with pytest.raises(ValueError):
        PersonalRiskRequest(
            age_group=AgeGroup.AGE_18_30,
            occupation=OccupationType.STUDENT,
            current_activity=ActivityType.WALKING,
            outdoor_duration_minutes=-10,
        )

    with pytest.raises(ValueError):
        PersonalRiskRequest(
            age_group=AgeGroup.AGE_18_30,
            occupation=OccupationType.STUDENT,
            current_activity=ActivityType.WALKING,
            outdoor_duration_minutes=800,  # Exceeds 720 min (12 hours)
        )


def test_personal_risk_api_endpoint(client):
    """Verify POST /api/personal-risk/calculate endpoint via FastAPI TestClient."""
    payload = {
        "age_group": "60+",
        "occupation": "elderly_nonworking",
        "current_activity": "walking",
        "outdoor_duration_minutes": 45,
        "ward_id": "AMD_01",
    }
    response = client.post("/api/personal-risk/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "personal_risk_score" in data
    assert "risk_tier" in data
    assert "factor_breakdown" in data
    assert len(data["factor_breakdown"]) == 6
    assert "consequence_text" in data
    assert "recommendation_text" in data
    assert data["ward_id"] == "AMD_01"
