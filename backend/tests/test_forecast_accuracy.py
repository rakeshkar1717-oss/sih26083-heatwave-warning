"""Unit tests for 72-Hour Forecast & Risk Classification Accuracy Engine."""

import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.validation.forecast_accuracy import (
    load_or_pull_summer_era5,
    compute_daily_ground_truth,
    simulate_3day_ahead_forecasts,
    evaluate_accuracy,
    run_full_accuracy_pipeline,
    VULNERABILITY_ARCHETYPES,
)
from backend.api.main import app


@pytest.fixture(scope="module")
def sample_daily_data():
    """Load cached multi-year ERA5 data and compute daily ground truth once for tests."""
    hourly_df = load_or_pull_summer_era5(use_cache=True)
    # Take a slice of the first 2 seasons for fast testing
    daily_df = compute_daily_ground_truth(hourly_df)
    return daily_df


def test_load_summer_era5_structure():
    """Verify that ERA5 multi-year data loads and conforms to weather schema."""
    df = load_or_pull_summer_era5(use_cache=True)
    assert not df.empty
    assert "timestamp" in df.columns
    assert "temp_c" in df.columns
    assert "humidity_pct" in df.columns
    assert "wind_speed_ms" in df.columns
    assert "solar_radiation_wm2" in df.columns
    assert len(df) >= 2000


def test_compute_daily_ground_truth(sample_daily_data):
    """Verify that daily ground truth aggregates thermal indices correctly."""
    daily = sample_daily_data
    assert not daily.empty
    assert "date" in daily.columns
    assert "temp_max" in daily.columns
    assert "hazard_max" in daily.columns
    assert "wbgt_max" in daily.columns
    assert "hi_max" in daily.columns

    # Check realistic physical bounds for Ahmedabad summer
    assert daily["temp_max"].max() >= 40.0
    assert daily["hazard_max"].max() > 60.0


def test_simulate_3day_ahead_forecasts(sample_daily_data):
    """Verify 72-hour lead prediction simulation across archetypes."""
    # Test on single archetype for speed
    test_archetypes = [VULNERABILITY_ARCHETYPES[1]]
    sim_df = simulate_3day_ahead_forecasts(sample_daily_data, archetypes=test_archetypes)

    assert not sim_df.empty
    assert "actual_tier" in sim_df.columns
    assert "pred_tier" in sim_df.columns
    assert "actual_risk" in sim_df.columns
    assert "pred_risk" in sim_df.columns
    assert "correct" in sim_df.columns

    # Verify predictions lie within physical 0.0 to 1.0 probability bounds
    assert (sim_df["actual_risk"] >= 0.0).all() and (sim_df["actual_risk"] <= 1.0).all()
    assert (sim_df["pred_risk"] >= 0.0).all() and (sim_df["pred_risk"] <= 1.0).all()


def test_evaluate_accuracy_metrics(sample_daily_data):
    """Verify that accuracy metrics calculate exact and within-1-tier values accurately."""
    sim_df = simulate_3day_ahead_forecasts(sample_daily_data, archetypes=VULNERABILITY_ARCHETYPES)
    results = evaluate_accuracy(sim_df)

    assert results["total_evaluations"] > 500
    assert 50.0 <= results["overall_accuracy_pct"] <= 95.0
    assert results["within_1_tier_pct"] >= results["overall_accuracy_pct"]
    assert results["within_1_tier_pct"] > 90.0

    cm = results["confusion_matrix"]
    assert isinstance(cm, pd.DataFrame)
    assert cm.values.sum() == results["total_evaluations"]

    # Verify continuous error metrics
    errs = results["continuous_errors"]
    assert 0.5 <= errs["temp_mae_c"] <= 3.0
    assert errs["risk_mae"] < 0.15


def test_api_forecast_accuracy_endpoint():
    """Verify FastAPI GET /api/validation/forecast-accuracy endpoint."""
    client = TestClient(app)
    response = client.get("/api/validation/forecast-accuracy")
    assert response.status_code == 200
    data = response.json()

    assert "overall_accuracy_pct" in data
    assert "within_1_tier_pct" in data
    assert "confusion_matrix" in data
    assert "tier_metrics" in data
    assert "bias" in data
    assert "continuous_errors" in data
    assert data["overall_accuracy_pct"] > 60.0
