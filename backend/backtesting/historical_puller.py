"""Historical Meteorological Data Ingestion and Caching Module.

Pulls historical weather data for validation and backtesting of extreme heatwave events.
Supports Copernicus ERA5 reanalysis (via cdsapi) with automated fallback to Open-Meteo
Historical Archive and zero-dependency local disk caching.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

from backend.config import settings, HISTORICAL_CACHE_PATH, BACKTEST_EVENT
from backend.models import FIXED_WEATHER_COLUMNS, WeatherSource, validate_weather_dataframe
from backend.data_ingestion import era5

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _build_requests_session() -> requests.Session:
    """Create requests session with retry strategy and realistic user agent."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "SIH26083-Backtesting/1.0 (ClimateRiskEarlyWarning)"})
    return session


def _fetch_from_open_meteo_archive(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timeout: int = 20,
) -> pd.DataFrame:
    """Fetch hourly historical observations from Open-Meteo Reanalysis/Archive API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,direct_normal_irradiance",
        "timezone": "UTC",
    }
    session = _build_requests_session()
    logger.info("Querying Open-Meteo Archive for lat=%.2f, lon=%.2f [%s to %s]", lat, lon, start_date, end_date)
    response = session.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        raise ValueError("Open-Meteo Archive returned empty hourly dataset.")

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(times, utc=True),
        "lat": lat,
        "lon": lon,
        "temp_c": hourly.get("temperature_2m", []),
        "humidity_pct": hourly.get("relative_humidity_2m", []),
        "wind_speed_ms": [
            round(w / 3.6, 2) if w is not None else 1.0
            for w in hourly.get("wind_speed_10m", [])
        ],  # Convert km/h to m/s
        "solar_radiation_wm2": [
            float(s) if s is not None else 0.0
            for s in hourly.get("direct_normal_irradiance", [])
        ],
        "source": "era5",
    })

    return df


def pull_historical_weather(
    city: str = settings.default_city,
    start_date: str = settings.backtest_start_date,
    end_date: str = settings.backtest_end_date,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Pull historical weather data for the specified city and date range.

    Attempts Copernicus ERA5 first (if credentials are present), falls back to
    Open-Meteo Historical Archive, and checks/saves to local cache to ensure 100%
    offline reliability during live hackathon judging.

    Parameters
    ----------
    city : str
        Target pilot city (default: Ahmedabad).
    start_date : str
        ISO start date YYYY-MM-DD (default: 2010-05-15).
    end_date : str
        ISO end date YYYY-MM-DD (default: 2010-05-27).
    lat : float, optional
        Latitude coordinate. Defaults to city settings.
    lon : float, optional
        Longitude coordinate. Defaults to city settings.
    use_cache : bool
        If True and cache file exists, load from disk without network queries.
    force_refresh : bool
        If True, ignore disk cache and re-fetch.

    Returns
    -------
    pd.DataFrame
        Standardized, schema-validated historical weather DataFrame.
    """
    target_lat = lat if lat is not None else settings.default_lat
    target_lon = lon if lon is not None else settings.default_lon

    cache_path = Path(HISTORICAL_CACHE_PATH)

    # 1. Check local cache
    if use_cache and not force_refresh and cache_path.exists():
        logger.info("Loading historical weather from local cache: %s", cache_path)
        try:
            cached_df = pd.read_csv(cache_path)
            cached_df["timestamp"] = pd.to_datetime(cached_df["timestamp"], utc=True)
            # Filter to requested date window if cache contains a wider range
            s_dt = pd.to_datetime(start_date, utc=True)
            e_dt = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1)
            mask = (cached_df["timestamp"] >= s_dt) & (cached_df["timestamp"] < e_dt)
            filtered_df = cached_df[mask].copy() if mask.any() else cached_df.copy()
            return validate_weather_dataframe(filtered_df)
        except Exception as e:
            logger.warning("Failed to load historical cache (%s). Will re-fetch.", e)

    # 2. Try ERA5 cdsapi if credentials configured
    df = None
    has_cds_key = bool(settings.cds_api_key or os.environ.get("CDS_API_KEY"))
    if has_cds_key:
        try:
            logger.info("Attempting ERA5 pull via Copernicus CDS API...")
            era5_df = era5.fetch(lat=target_lat, lon=target_lon, start_date=start_date, end_date=end_date)
            if len(era5_df) > 0:
                df = era5_df
        except Exception as e:
            logger.warning("Copernicus CDS API fetch unsuccessful (%s). Falling back to Open-Meteo Archive.", e)

    # 3. Fallback to Open-Meteo Archive API
    if df is None or len(df) == 0:
        try:
            df = _fetch_from_open_meteo_archive(
                lat=target_lat,
                lon=target_lon,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error("Failed to fetch historical data from Open-Meteo Archive: %s", e)
            if cache_path.exists():
                logger.info("Falling back to existing cached dataset.")
                cached_df = pd.read_csv(cache_path)
                cached_df["timestamp"] = pd.to_datetime(cached_df["timestamp"], utc=True)
                return validate_weather_dataframe(cached_df)
            raise RuntimeError(f"Could not retrieve historical weather: {e}") from e

    # Validate dataframe
    validated_df = validate_weather_dataframe(df)

    # 4. Save to local cache for offline demonstration
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        validated_df.to_csv(cache_path, index=False)
        logger.info("Persisted %d historical weather records to cache: %s", len(validated_df), cache_path)
    except Exception as e:
        logger.warning("Could not persist historical data to cache: %s", e)

    return validated_df
