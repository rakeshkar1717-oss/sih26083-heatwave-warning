"""Unit tests for Thermal Stress Indices against NOAA benchmarks and physical sensitivity."""

from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

from backend.index_calculation import (
    calculate_heat_index,
    calculate_wbgt,
    calculate_utci,
    compute_thermal_indices,
)
from backend.models import FIXED_WEATHER_COLUMNS, WeatherSource


# ==============================================================================
# 1. NOAA Heat Index Benchmark Tests
# ==============================================================================

def test_noaa_heat_index_standard_benchmarks():
    """Verify calculated Heat Index against NOAA official lookup table values within 1.0°C tolerance.

    NOAA Lookup Table Reference Points:
    1. 90°F (32.22°C), 50% RH -> 96°F (35.56°C)
    2. 94°F (34.44°C), 60% RH -> 110°F (43.33°C)
    3. 100°F (37.78°C), 40% RH -> 109°F (42.78°C)
    """
    # Test case 1: 90°F, 50% RH
    hi_1 = calculate_heat_index(32.22, 50.0)
    assert abs(hi_1 - 35.56) < 1.0, f"Expected ~35.56°C, got {hi_1}°C"

    # Test case 2: 94°F, 60% RH
    hi_2 = calculate_heat_index(34.44, 60.0)
    assert abs(hi_2 - 43.33) < 1.0, f"Expected ~43.33°C, got {hi_2}°C"

    # Test case 3: 100°F, 40% RH
    hi_3 = calculate_heat_index(37.78, 40.0)
    assert abs(hi_3 - 42.78) < 1.0, f"Expected ~42.78°C, got {hi_3}°C"


def test_noaa_heat_index_mild_temperatures():
    """Under mild conditions (< 20°C / 68°F), Heat Index should track air temperature closely."""
    hi_mild = calculate_heat_index(18.0, 50.0)
    assert abs(hi_mild - 18.0) < 2.0


def test_heat_index_vectorized_series():
    """Test pandas Series input and output preservation."""
    temps = pd.Series([30.0, 35.0, 40.0])
    rhs = pd.Series([40.0, 50.0, 60.0])
    res = calculate_heat_index(temps, rhs)
    assert isinstance(res, pd.Series)
    assert len(res) == 3
    assert res.iloc[2] > res.iloc[1] > res.iloc[0]


# ==============================================================================
# 2. Outdoor WBGT Sensitivity Tests
# ==============================================================================

def test_wbgt_solar_sensitivity():
    """Outdoor WBGT must be higher under bright solar irradiance than in shade/night."""
    temp = 35.0
    rh = 50.0
    wind = 2.0

    wbgt_night = calculate_wbgt(temp, rh, wind, solar_radiation_wm2=0.0)
    wbgt_sun = calculate_wbgt(temp, rh, wind, solar_radiation_wm2=900.0)

    assert wbgt_sun > wbgt_night, f"Sunny WBGT ({wbgt_sun}) must exceed night WBGT ({wbgt_night})"
    # Solar irradiance typically adds 3°C to 8°C to outdoor WBGT
    assert (wbgt_sun - wbgt_night) >= 3.0


def test_wbgt_wind_cooling_effect():
    """High wind speeds must dissipate heat and lower outdoor WBGT compared to stagnant air."""
    temp = 38.0
    rh = 45.0
    solar = 800.0

    wbgt_stagnant = calculate_wbgt(temp, rh, wind_speed_ms=0.5, solar_radiation_wm2=solar)
    wbgt_breezy = calculate_wbgt(temp, rh, wind_speed_ms=5.0, solar_radiation_wm2=solar)

    assert wbgt_breezy < wbgt_stagnant, "Wind should reduce WBGT through forced convective cooling"


# ==============================================================================
# 3. Operational UTCI Sensitivity Tests
# ==============================================================================

def test_utci_physical_bounds():
    """UTCI must produce sensible physical equivalent temperatures for hot summer days."""
    utci_moderate = calculate_utci(temp_c=30.0, humidity_pct=40.0, wind_speed_ms=2.0, solar_radiation_wm2=300.0)
    utci_extreme = calculate_utci(temp_c=42.0, humidity_pct=50.0, wind_speed_ms=1.0, solar_radiation_wm2=950.0)

    assert 25.0 <= utci_moderate <= 40.0, f"Moderate UTCI out of expected range: {utci_moderate}"
    assert utci_extreme > 42.0, f"Extreme UTCI should exceed 42°C: {utci_extreme}"


# ==============================================================================
# 4. Integrated Index Engine Tests
# ==============================================================================

def test_compute_thermal_indices_dataframe():
    """Ensure compute_thermal_indices enriches Day 1 dataframe with valid schemas."""
    sample_df = pd.DataFrame({
        "timestamp": [datetime.now(timezone.utc), datetime.now(timezone.utc)],
        "lat": [23.03, 23.03],
        "lon": [72.58, 72.58],
        "temp_c": [33.0, 41.5],
        "humidity_pct": [60.0, 35.0],
        "wind_speed_ms": [2.5, 1.8],
        "solar_radiation_wm2": [450.0, 850.0],
        "source": [WeatherSource.OPEN_METEO.value, WeatherSource.OPEN_METEO.value],
    })

    enriched = compute_thermal_indices(sample_df)

    expected_new_cols = ["heat_index_c", "wbgt_c", "utci_c", "thermal_stress_score", "stress_category"]
    for col in expected_new_cols:
        assert col in enriched.columns, f"Missing expected column: {col}"

    # Verify score bounds [0.0, 100.0]
    for score in enriched["thermal_stress_score"]:
        assert 0.0 <= score <= 100.0

    # The hotter condition (row 1: 41.5°C) must have higher score than row 0 (33.0°C)
    assert enriched["thermal_stress_score"].iloc[1] > enriched["thermal_stress_score"].iloc[0]


def test_compute_thermal_indices_empty():
    """Ensure graceful handling of empty DataFrame."""
    empty_df = pd.DataFrame(columns=FIXED_WEATHER_COLUMNS)
    res = compute_thermal_indices(empty_df)
    assert "thermal_stress_score" in res.columns
    assert len(res) == 0
