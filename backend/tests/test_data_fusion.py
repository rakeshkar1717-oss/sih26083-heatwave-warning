"""Tests for multi-source meteorological data fusion and multi-horizon accuracy validation."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from backend.models import WeatherSource, FIXED_WEATHER_COLUMNS, validate_weather_dataframe
from backend.data_ingestion.data_fusion import fuse_weather_sources, DEFAULT_FUSION_WEIGHTS
from backend.config import DEFAULT_RISK_TIER_THRESHOLDS, TUNED_RISK_TIER_THRESHOLDS
from backend.forecasting.forecast_engine import _classify_risk_tier
from backend.validation.multi_horizon_backtest import (
    compute_daily_ground_truth,
    simulate_multi_horizon_forecasts,
    evaluate_stage_metrics,
)


@pytest.fixture
def sample_om_df():
    """Create a minimal synthetic Open-Meteo hourly DataFrame."""
    times = [datetime(2024, 5, 1, h, 0, tzinfo=timezone.utc) for h in range(24)]
    return pd.DataFrame({
        "timestamp": times,
        "lat": [23.03] * 24,
        "lon": [72.58] * 24,
        "temp_c": [30.0 + h * 0.5 for h in range(24)],
        "humidity_pct": [40.0 - h * 0.5 for h in range(24)],
        "wind_speed_ms": [3.0] * 24,
        "solar_radiation_wm2": [500.0] * 24,
        "source": [WeatherSource.OPEN_METEO.value] * 24,
    })


@pytest.fixture
def sample_np_df():
    """Create a minimal synthetic NASA POWER hourly DataFrame with slight offset."""
    times = [datetime(2024, 5, 1, h, 0, tzinfo=timezone.utc) for h in range(24)]
    return pd.DataFrame({
        "timestamp": times,
        "lat": [23.03] * 24,
        "lon": [72.58] * 24,
        "temp_c": [32.0 + h * 0.5 for h in range(24)],
        "humidity_pct": [36.0 - h * 0.5 for h in range(24)],
        "wind_speed_ms": [4.0] * 24,
        "solar_radiation_wm2": [550.0] * 24,
        "source": [WeatherSource.NASA_POWER.value] * 24,
    })


def test_fuse_weather_sources_equal_weights(sample_om_df, sample_np_df):
    """Verify that fuse_weather_sources calculates correct 50/50 consensus."""
    fused = fuse_weather_sources(sample_om_df, sample_np_df)
    assert len(fused) == 24
    assert list(fused.columns) == FIXED_WEATHER_COLUMNS
    assert fused["source"].iloc[0] == WeatherSource.FUSED_OM_NASA.value

    # First hour: (30.0 + 32.0) / 2 = 31.0
    assert np.isclose(fused["temp_c"].iloc[0], 31.0, atol=0.05)
    # Humidity: (40.0 + 36.0) / 2 = 38.0
    assert np.isclose(fused["humidity_pct"].iloc[0], 38.0, atol=0.05)
    # Wind: (3.0 + 4.0) / 2 = 3.5
    assert np.isclose(fused["wind_speed_ms"].iloc[0], 3.5, atol=0.05)
    # Solar: (500.0 + 550.0) / 2 = 525.0
    assert np.isclose(fused["solar_radiation_wm2"].iloc[0], 525.0, atol=0.05)


def test_fuse_weather_sources_fallback_on_empty(sample_om_df, sample_np_df):
    """Verify graceful fallback when one source DataFrame is empty."""
    empty_df = pd.DataFrame()
    fused_om_only = fuse_weather_sources(sample_om_df, empty_df)
    assert len(fused_om_only) == 24
    assert fused_om_only["source"].iloc[0] == WeatherSource.FUSED_OM_NASA.value

    fused_np_only = fuse_weather_sources(empty_df, sample_np_df)
    assert len(fused_np_only) == 24
    assert fused_np_only["source"].iloc[0] == WeatherSource.FUSED_OM_NASA.value


def test_classify_risk_tier_with_thresholds():
    """Verify that _classify_risk_tier properly respects custom tuned thresholds."""
    score = 0.49
    # In default (MODERATE upper bound is 0.50), 0.49 is MODERATE
    tier_default = _classify_risk_tier(score, thresholds=DEFAULT_RISK_TIER_THRESHOLDS)
    assert tier_default == "MODERATE"

    # In tuned (MODERATE upper bound is 0.48), 0.49 is HIGH
    tier_tuned = _classify_risk_tier(score, thresholds=TUNED_RISK_TIER_THRESHOLDS)
    assert tier_tuned == "HIGH"


def test_evaluate_stage_metrics_computation():
    """Verify that evaluate_stage_metrics accurately computes accuracy and matrices."""
    records = []
    for i in range(100):
        actual = "HIGH" if i < 60 else "VERY_HIGH"
        pred = actual if i % 10 != 0 else "MODERATE"  # 90% accuracy
        records.append({
            "stage": "Test",
            "archetype": "City Median",
            "date": datetime(2024, 5, 1).date(),
            "horizon": (i % 5) + 1,
            "actual_temp_c": 42.0,
            "pred_temp_c": 41.5,
            "actual_hazard": 70.0,
            "pred_hazard": 68.0,
            "actual_risk": 0.65,
            "pred_risk": 0.64,
            "actual_tier": actual,
            "pred_tier": pred,
            "correct": (actual == pred),
        })
    df = pd.DataFrame(records)
    metrics = evaluate_stage_metrics(df)

    assert metrics["total_evaluations"] == 100
    assert metrics["correct_predictions"] == 90
    assert metrics["overall_accuracy_pct"] == 90.0
    assert 1 in metrics["horizon_metrics"]
    assert "HIGH" in metrics["tier_metrics"]
    assert metrics["tier_metrics"]["HIGH"]["support"] == 60
