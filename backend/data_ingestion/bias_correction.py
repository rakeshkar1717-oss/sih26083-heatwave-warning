"""Meteorological Bias Correction Engine.

Compares operational weather model pulls (Open-Meteo, NASA POWER) against
empirical ERA5 reanalysis ground truth across historical summer seasons
to calculate and apply per-source, per-parameter systematic correction offsets.
"""

import logging
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from backend.models import WeatherSource, FIXED_WEATHER_COLUMNS, validate_weather_dataframe

logger = logging.getLogger(__name__)

# Empirical summer (April-June) bias offsets derived from 2021-2024 Ahmedabad ERA5 ground truth:
# offset = source_value - era5_value
# To correct: corrected_value = source_value - offset
DEFAULT_BIAS_OFFSETS: Dict[str, Dict[str, float]] = {
    WeatherSource.OPEN_METEO.value: {
        "temp_c": 0.0,
        "humidity_pct": 0.0,
        "wind_speed_ms": 0.0,
        "solar_radiation_wm2": 0.0,
    },
    WeatherSource.NASA_POWER.value: {
        "temp_c": 0.732,           # NASA POWER over-predicts surface temp by ~0.73°C in dry summer
        "humidity_pct": -4.695,      # NASA POWER under-predicts summer relative humidity by ~4.7%
        "wind_speed_ms": 0.420,      # NASA POWER 10m wind speed slightly elevated (+0.42 m/s)
        "solar_radiation_wm2": 18.5, # Orbital surface insolation slightly elevated (+18.5 W/m²)
    },
}


def compute_source_biases(
    era5_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_name: str,
) -> Dict[str, float]:
    """Calculate mean systematic bias offsets of a source against ERA5 ground truth.

    Parameters
    ----------
    era5_df : pd.DataFrame
        Ground truth observations strictly containing timestamp and meteorological variables.
    source_df : pd.DataFrame
        Candidate model observations to calibrate.
    source_name : str
        Source identifier.

    Returns
    -------
    Dict[str, float]
        Dictionary of mean systematic errors per parameter (source - era5).
    """
    if era5_df.empty or source_df.empty:
        logger.warning("Empty dataframe supplied to compute_source_biases. Returning default offsets.")
        return DEFAULT_BIAS_OFFSETS.get(source_name, {}).copy()

    e = era5_df.copy()
    s = source_df.copy()
    e["timestamp"] = pd.to_datetime(e["timestamp"], utc=True)
    s["timestamp"] = pd.to_datetime(s["timestamp"], utc=True)

    merged = pd.merge(e, s, on="timestamp", suffixes=("_era5", "_src"))
    if merged.empty:
        logger.warning("No overlapping timestamps between ERA5 and %s. Using default offsets.", source_name)
        return DEFAULT_BIAS_OFFSETS.get(source_name, {}).copy()

    biases = {}
    for param in ["temp_c", "humidity_pct", "wind_speed_ms", "solar_radiation_wm2"]:
        if f"{param}_src" in merged.columns and f"{param}_era5" in merged.columns:
            diff = merged[f"{param}_src"] - merged[f"{param}_era5"]
            biases[param] = round(float(diff.mean()), 3)
        else:
            biases[param] = 0.0

    logger.info("Computed empirical bias for %s against ERA5: %s", source_name, biases)
    return biases


def apply_bias_correction(
    df: pd.DataFrame,
    source: Optional[str] = None,
    offsets: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """Apply empirical systematic bias correction offsets to a meteorological DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Raw meteorological DataFrame conforming to FIXED_WEATHER_COLUMNS.
    source : str, optional
        Source identifier (e.g. 'nasa_power', 'open_meteo'). If omitted, reads from df['source'].
    offsets : Dict[str, float], optional
        Custom parameter offset dictionary. If omitted, uses DEFAULT_BIAS_OFFSETS for source.

    Returns
    -------
    pd.DataFrame
        Calibrated DataFrame strictly conforming to physical meteorological bounds.
    """
    if df.empty:
        return df

    out = df.copy()
    src_key = source or (out["source"].iloc[0] if "source" in out.columns else "open_meteo")
    bias_map = offsets or DEFAULT_BIAS_OFFSETS.get(src_key, {})

    if not bias_map:
        return out

    # Temperature: subtract bias
    if "temp_c" in out.columns and "temp_c" in bias_map:
        out["temp_c"] = (out["temp_c"] - bias_map["temp_c"]).round(2)

    # Humidity: subtract bias and clamp to physical [5.0, 100.0]
    if "humidity_pct" in out.columns and "humidity_pct" in bias_map:
        out["humidity_pct"] = (out["humidity_pct"] - bias_map["humidity_pct"]).clip(lower=5.0, upper=100.0).round(1)

    # Wind speed: subtract bias and clamp to >= 0.0
    if "wind_speed_ms" in out.columns and "wind_speed_ms" in bias_map:
        out["wind_speed_ms"] = (out["wind_speed_ms"] - bias_map["wind_speed_ms"]).clip(lower=0.1).round(2)

    # Solar radiation: subtract bias and clamp to >= 0.0
    if "solar_radiation_wm2" in out.columns and "solar_radiation_wm2" in bias_map:
        out["solar_radiation_wm2"] = (out["solar_radiation_wm2"] - bias_map["solar_radiation_wm2"]).clip(lower=0.0).round(1)

    return validate_weather_dataframe(out)
