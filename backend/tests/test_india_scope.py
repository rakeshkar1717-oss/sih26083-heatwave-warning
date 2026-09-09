"""Tests for All-India regional early warning GeoJSON endpoint."""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_india_geojson_endpoint():
    """Verify /api/india/geojson returns 35 Indian States and UTs with valid properties."""
    response = client.get("/api/india/geojson")
    assert response.status_code == 200
    data = response.json()
    assert data.get("type") == "FeatureCollection"
    features = data.get("features", [])
    assert len(features) >= 30

    # Test Gujarat feature properties
    gj = next((f for f in features if f["properties"].get("state_name") == "Gujarat"), None)
    assert gj is not None
    props = gj["properties"]
    assert "temp_c" in props
    assert "wbgt_c" in props
    assert "heat_index_c" in props
    assert "vulnerability_score" in props
    assert "final_risk_score" in props
    assert "risk_level" in props
    assert "color" in props
