"""NASA POWER Meteorological Data Fetcher.

Fetches hourly solar and meteorological data from the NASA POWER API (no key required).
Returns a standardized DataFrame strictly conforming to FIXED_WEATHER_COLUMNS.
"""

from datetime import datetime
import logging
from typing import Optional
import numpy as np
import pandas as pd
import requests

from backend.models import FIXED_WEATHER_COLUMNS, WeatherSource, validate_weather_dataframe

logger = logging.getLogger(__name__)

NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"


def _format_nasa_date(date_str: str) -> str:
    """Format date to NASA POWER YYYYMMDD string format."""
    clean = date_str.replace("-", "").replace("/", "").strip()
    if len(clean) >= 8 and clean[:8].isdigit():
        return clean[:8]
    raise ValueError(f"Cannot parse date '{date_str}' into NASA POWER format YYYYMMDD.")


def fetch(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timeout: int = 30,
    session: Optional[requests.Session] = None
) -> pd.DataFrame:
    """Fetch hourly weather data from NASA POWER API.

    Parameters
    ----------
    lat : float
        Latitude in decimal degrees (-90 to 90).
    lon : float
        Longitude in decimal degrees (-180 to 180).
    start_date : str
        Start date string (e.g. '2024-05-01' or '20240501').
    end_date : str
        End date string (e.g. '2024-05-03' or '20240503').
    timeout : int, optional
        HTTP request timeout in seconds, by default 30.
    session : requests.Session, optional
        Custom session for pooling or testing, by default None.

    Returns
    -------
    pd.DataFrame
        Standardized DataFrame with columns:
        [timestamp, lat, lon, temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2, source]

    Raises
    ------
    ValueError
        If inputs are invalid or response payload is corrupted.
    requests.RequestException
        If the HTTP request fails.
    """
    nasa_start = _format_nasa_date(start_date)
    nasa_end = _format_nasa_date(end_date)

    params = {
        "parameters": "T2M,RH2M,WS10M,ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": nasa_start,
        "end": nasa_end,
        "format": "JSON",
    }

    http = session or requests
    logger.info("Fetching NASA POWER data for (%.4f, %.4f) from %s to %s", lat, lon, nasa_start, nasa_end)

    try:
        response = http.get(NASA_POWER_BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("NASA POWER request failed: %s", exc)
        raise

    parameters = data.get("properties", {}).get("parameter", {})
    t2m = parameters.get("T2M", {})
    rh2m = parameters.get("RH2M", {})
    ws10m = parameters.get("WS10M", {})
    solar = parameters.get("ALLSKY_SFC_SW_DWN", {})

    if not t2m:
        logger.warning("NASA POWER returned no hourly observations.")
        empty_df = pd.DataFrame(columns=FIXED_WEATHER_COLUMNS)
        return validate_weather_dataframe(empty_df)

    # Collect sorted unique timestamps in format YYYYMMDDHH
    all_timestamps = sorted(t2m.keys())

    # Build DataFrame
    records = []
    for ts_str in all_timestamps:
        dt = datetime.strptime(ts_str, "%Y%m%d%H")

        # NASA POWER flags missing values with -999.0
        val_t = t2m.get(ts_str, np.nan)
        val_rh = rh2m.get(ts_str, np.nan)
        val_ws = ws10m.get(ts_str, np.nan)
        val_sol = solar.get(ts_str, np.nan)

        records.append({
            "timestamp": pd.to_datetime(dt, utc=True),
            "lat": float(lat),
            "lon": float(lon),
            "temp_c": np.nan if val_t == -999.0 else val_t,
            "humidity_pct": np.nan if val_rh == -999.0 else val_rh,
            "wind_speed_ms": np.nan if val_ws == -999.0 else val_ws,
            "solar_radiation_wm2": 0.0 if (val_sol == -999.0 or val_sol < 0) else val_sol,
            "source": WeatherSource.NASA_POWER.value,
        })

    df = pd.DataFrame(records)

    # Interpolate minor missing points if any
    for col in ["temp_c", "humidity_pct", "wind_speed_ms"]:
        if df[col].isna().any():
            df[col] = df[col].interpolate(method="linear").bfill().ffill()

    return validate_weather_dataframe(df)
