"""Tests for bias correction and multi-source weighted data fusion."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from backend.models import WeatherSource, FIXED_WEATHER_COLUMNS
from backend.data_ingestion.bias_correction import (
    compute_source_biases,
    apply_bias_correction,
    DEFAULT_BIAS_OFFSETS,
)
from backend.data_ingestion.fusion import (
    fuse_sources,
    compute_optimal_weights,
    OPTIMAL_FUSION_WEIGHTS,
)


@pytest.fixture
def synthetic_era5():
    times = [datetime(2024, 5, 1, h, 0, tzinfo=timezone.utc) for h in range(24)]
    return pd.DataFrame({
        "timestamp": times,
        "lat": [23.03] * 24,
        "lon": [72.58] * 24,
        "temp_c": [35.0] * 24,
        "humidity_pct": [30.0] * 24,
        "wind_speed_ms": [3.0] * 24,
        "solar_radiation_wm2": [600.0] * 24,
        "source": [WeatherSource.ERA5.value] * 24,
    })


@pytest.fixture
def synthetic_om(synthetic_era5):
    df = synthetic_era5.copy()
    df["source"] = WeatherSource.OPEN_METEO.value
    df["temp_c"] = [35.2] * 24          # +0.2C bias
    df["humidity_pct"] = [29.0] * 24    # -1.0% bias
    return df


@pytest.fixture
def synthetic_np(synthetic_era5):
    df = synthetic_era5.copy()
    df["source"] = WeatherSource.NASA_POWER.value
    df["temp_c"] = [36.0] * 24          # +1.0C bias
    df["humidity_pct"] = [25.0] * 24    # -5.0% bias
    return df


def test_compute_source_biases(synthetic_era5, synthetic_np):
    biases = compute_source_biases(synthetic_era5, synthetic_np, WeatherSource.NASA_POWER.value)
    assert np.isclose(biases["temp_c"], 1.0, atol=0.01)
    assert np.isclose(biases["humidity_pct"], -5.0, atol=0.01)


def test_apply_bias_correction(synthetic_np):
    offsets = {"temp_c": 1.0, "humidity_pct": -5.0}
    corrected = apply_bias_correction(synthetic_np, offsets=offsets)
    # Original was 36.0C, offset was 1.0 -> 35.0C
    assert np.isclose(corrected["temp_c"].iloc[0], 35.0, atol=0.01)
    # Original was 25.0%, offset was -5.0 -> 30.0%
    assert np.isclose(corrected["humidity_pct"].iloc[0], 30.0, atol=0.01)


def test_compute_optimal_weights(synthetic_era5, synthetic_om, synthetic_np):
    # OM has MAE=0.2C, NP has MAE=1.0C.
    # Inverse MAE: inv_om = 1/0.2 = 5, inv_np = 1/1.0 = 1. Total = 6.
    # Expected w_om = 5/6 = 0.833, w_np = 1/6 = 0.167
    weights = compute_optimal_weights(synthetic_era5, synthetic_om, synthetic_np)
    w_om_t, w_np_t = weights["temp_c"]
    assert w_om_t > w_np_t
    assert np.isclose(w_om_t, 0.833, atol=0.01)


def test_fuse_sources_with_bias_correction(synthetic_om, synthetic_np):
    fused = fuse_sources(synthetic_om, synthetic_np, apply_bias=True)
    assert len(fused) == 24
    assert list(fused.columns) == FIXED_WEATHER_COLUMNS
    assert fused["source"].iloc[0] == WeatherSource.FUSED_OM_NASA.value
    # Both temperatures were adjusted and fused into reasonable range
    assert 30.0 <= fused["temp_c"].iloc[0] <= 45.0
