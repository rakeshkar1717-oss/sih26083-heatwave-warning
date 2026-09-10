"""Multi-Source Meteorological Data Fusion Layer.

Combines ground and satellite observations from Open-Meteo and NASA POWER
to reduce sensor drift, mitigate localized microclimatic bias, and produce
a robust, consensus-driven meteorological input for biometeorological modeling.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from backend.config import CACHE_DATA_DIR
from backend.models import (
    FIXED_WEATHER_COLUMNS,
    WeatherSource,
    validate_weather_dataframe,
)
from backend.data_ingestion import open_meteo, nasa_power

logger = logging.getLogger(__name__)

# Default 50/50 balance across meteorological parameters (Open-Meteo, NASA POWER)
DEFAULT_FUSION_WEIGHTS: Dict[str, Tuple[float, float]] = {
    "temp_c": (0.50, 0.50),
    "humidity_pct": (0.50, 0.50),
    "wind_speed_ms": (0.50, 0.50),
    "solar_radiation_wm2": (0.50, 0.50),
}


def fuse_weather_sources(
    df_open_meteo: pd.DataFrame,
    df_nasa_power: pd.DataFrame,
    weights: Optional[Dict[str, Tuple[float, float]]] = None,
) -> pd.DataFrame:
    """Fuse Open-Meteo and NASA POWER hourly weather observations into a unified consensus dataset.

    Parameters
    ----------
    df_open_meteo : pd.DataFrame
        Hourly observations from Open-Meteo adhering to FIXED_WEATHER_COLUMNS.
    df_nasa_power : pd.DataFrame
        Hourly observations from NASA POWER adhering to FIXED_WEATHER_COLUMNS.
    weights : Dict[str, Tuple[float, float]], optional
        Tuple of (w_om, w_np) for each meteorological parameter.

    Returns
    -------
    pd.DataFrame
        Standardized consensus DataFrame conforming to FIXED_WEATHER_COLUMNS with source='fused_om_nasa'.
    """
    if df_open_meteo.empty and df_nasa_power.empty:
        raise ValueError("Both Open-Meteo and NASA POWER DataFrames are empty. Cannot perform data fusion.")
    if df_open_meteo.empty:
        logger.warning("Open-Meteo dataset is empty; falling back exclusively to NASA POWER.")
        res = df_nasa_power.copy()
        res["source"] = "fused_om_nasa"
        return validate_weather_dataframe(res)
    if df_nasa_power.empty:
        logger.warning("NASA POWER dataset is empty; falling back exclusively to Open-Meteo.")
        res = df_open_meteo.copy()
        res["source"] = "fused_om_nasa"
        return validate_weather_dataframe(res)

    active_weights = weights or DEFAULT_FUSION_WEIGHTS

    # Ensure UTC datetime indexing
    om = df_open_meteo.copy()
    np_df = df_nasa_power.copy()
    om["timestamp"] = pd.to_datetime(om["timestamp"], utc=True)
    np_df["timestamp"] = pd.to_datetime(np_df["timestamp"], utc=True)

    # Outer merge to preserve all hourly timestamps
    merged = pd.merge(
        om,
        np_df,
        on="timestamp",
        how="outer",
        suffixes=("_om", "_np"),
    ).sort_values("timestamp").reset_index(drop=True)

    lat = float(om["lat"].dropna().iloc[0]) if not om["lat"].dropna().empty else float(np_df["lat"].dropna().iloc[0])
    lon = float(om["lon"].dropna().iloc[0]) if not om["lon"].dropna().empty else float(np_df["lon"].dropna().iloc[0])

    records = []
    for _, row in merged.iterrows():
        ts = row["timestamp"]
        rec = {
            "timestamp": ts,
            "lat": lat,
            "lon": lon,
            "source": "fused_om_nasa",
        }

        for param in ["temp_c", "humidity_pct", "wind_speed_ms", "solar_radiation_wm2"]:
            w_om, w_np = active_weights.get(param, (0.50, 0.50))
            val_om = row.get(f"{param}_om")
            val_np = row.get(f"{param}_np")

            # Handle missing values gracefully
            has_om = pd.notna(val_om) and val_om != -999.0
            has_np = pd.notna(val_np) and val_np != -999.0

            if has_om and has_np:
                fused_val = w_om * float(val_om) + w_np * float(val_np)
            elif has_om:
                fused_val = float(val_om)
            elif has_np:
                fused_val = float(val_np)
            else:
                fused_val = np.nan

            rec[param] = fused_val

        records.append(rec)

    fused_df = pd.DataFrame(records)

    # Linear interpolation for any remaining boundary gaps
    for col in ["temp_c", "humidity_pct", "wind_speed_ms", "solar_radiation_wm2"]:
        if fused_df[col].isna().any():
            fused_df[col] = fused_df[col].interpolate(method="linear").bfill().ffill()

    # Round appropriately
    fused_df["temp_c"] = fused_df["temp_c"].round(2)
    fused_df["humidity_pct"] = fused_df["humidity_pct"].round(1)
    fused_df["wind_speed_ms"] = fused_df["wind_speed_ms"].round(2)
    fused_df["solar_radiation_wm2"] = fused_df["solar_radiation_wm2"].round(1)

    return validate_weather_dataframe(fused_df)


def fetch_fused_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
    **kwargs
) -> pd.DataFrame:
    """Fetch and fuse weather observations concurrently across Open-Meteo and NASA POWER.

    Parameters
    ----------
    lat : float
        Latitude coordinate.
    lon : float
        Longitude coordinate.
    start_date : str
        Start date string (YYYY-MM-DD).
    end_date : str
        End date string (YYYY-MM-DD).
    use_cache : bool
        Whether to check and store to local cache.
    cache_path : Path, optional
        Custom cache file path.

    Returns
    -------
    pd.DataFrame
        Fused consensus DataFrame strictly adhering to FIXED_WEATHER_COLUMNS.
    """
    clean_s = start_date.replace("-", "")
    clean_e = end_date.replace("-", "")
    default_cache = CACHE_DATA_DIR / f"fused_weather_{lat:.2f}_{lon:.2f}_{clean_s}_{clean_e}.csv"
    target_cache = cache_path or default_cache

    if use_cache and target_cache.exists():
        try:
            logger.info("Loading fused weather from local cache: %s", target_cache)
            cached_df = pd.read_csv(target_cache)
            cached_df["timestamp"] = pd.to_datetime(cached_df["timestamp"], utc=True)
            return validate_weather_dataframe(cached_df)
        except Exception as e:
            logger.warning("Failed to load cached fused weather (%s). Re-fetching.", e)

    logger.info("Fetching Open-Meteo and NASA POWER for fusion: (%.4f, %.4f) [%s to %s]", lat, lon, start_date, end_date)
    df_om = open_meteo.fetch(lat=lat, lon=lon, start_date=start_date, end_date=end_date, **kwargs)
    df_np = nasa_power.fetch(lat=lat, lon=lon, start_date=start_date, end_date=end_date, **kwargs)

    fused_df = fuse_weather_sources(df_om, df_np)

    if use_cache:
        try:
            target_cache.parent.mkdir(parents=True, exist_ok=True)
            fused_df.to_csv(target_cache, index=False)
            logger.info("Persisted fused weather dataset to cache: %s", target_cache)
        except Exception as err:
            logger.warning("Could not persist fused dataset to cache: %s", err)

    return fused_df
