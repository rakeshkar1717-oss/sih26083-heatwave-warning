"""Open-Meteo Weather Data Fetcher.

Fetches historical and forecast hourly weather data from Open-Meteo API (no key required).
Returns a standardized DataFrame strictly conforming to FIXED_WEATHER_COLUMNS.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.models import FIXED_WEATHER_COLUMNS, WeatherSource, validate_weather_dataframe

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _get_default_session() -> requests.Session:
    """Create a robust requests Session with automatic retries and custom User-Agent."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "SIH26083-HeatwaveEarlyWarning/1.0"})
    return session


def _normalize_date_str(date_str: str) -> str:
    """Normalize arbitrary date string (YYYY-MM-DD or YYYYMMDD) to YYYY-MM-DD format."""
    clean_date = date_str.replace("/", "-").strip()
    if len(clean_date) == 8 and clean_date.isdigit():
        return f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"
    return clean_date


def fetch(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timeout: int = 20,
    session: Optional[requests.Session] = None
) -> pd.DataFrame:
    """Fetch hourly weather data from Open-Meteo API.

    Parameters
    ----------
    lat : float
        Latitude in decimal degrees (-90 to 90).
    lon : float
        Longitude in decimal degrees (-180 to 180).
    start_date : str
        Start date string (e.g. '2026-09-01' or '20260901').
    end_date : str
        End date string (e.g. '2026-09-03' or '20260903').
    timeout : int, optional
        HTTP request timeout in seconds, by default 20.
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
    norm_start = _normalize_date_str(start_date)
    norm_end = _normalize_date_str(end_date)

    # Determine whether archive endpoint or forecast endpoint is needed
    try:
        req_start = datetime.strptime(norm_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        today = datetime.now(timezone.utc)
        # If the requested period is more than 3 months in the past, use archive
        days_ago = (today - req_start).days
        base_url = OPEN_METEO_ARCHIVE_URL if days_ago > 80 else OPEN_METEO_FORECAST_URL
    except ValueError:
        base_url = OPEN_METEO_FORECAST_URL

    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation_instant",
        "wind_speed_unit": "ms",
        "start_date": norm_start,
        "end_date": norm_end,
        "timezone": "UTC",
    }

    http = session or _get_default_session()
    logger.info("Fetching Open-Meteo data for (%.4f, %.4f) from %s to %s", lat, lon, norm_start, norm_end)

    try:
        response = http.get(base_url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        # Fallback to archive URL if forecast rejected past dates
        if base_url == OPEN_METEO_FORECAST_URL and hasattr(exc, "response") and exc.response is not None and exc.response.status_code == 400:
            logger.warning("Forecast API rejected date range; attempting Open-Meteo Archive API.")
            response = http.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        else:
            logger.error("Open-Meteo request failed: %s", exc)
            raise

    if "hourly" not in data:
        raise ValueError(f"Open-Meteo response missing 'hourly' section: {data.get('reason', 'Unknown error')}")

    hourly = data["hourly"]
    times = hourly.get("time", [])
    if not times:
        logger.warning("Open-Meteo returned 0 hourly entries for date range %s to %s", norm_start, norm_end)
        empty_df = pd.DataFrame(columns=FIXED_WEATHER_COLUMNS)
        return validate_weather_dataframe(empty_df)

    n_rows = len(times)
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(times, utc=True),
        "lat": float(lat),
        "lon": float(lon),
        "temp_c": hourly.get("temperature_2m", [None] * n_rows),
        "humidity_pct": hourly.get("relative_humidity_2m", [None] * n_rows),
        "wind_speed_ms": hourly.get("wind_speed_10m", [None] * n_rows),
        "solar_radiation_wm2": hourly.get("shortwave_radiation_instant", [None] * n_rows),
        "source": WeatherSource.OPEN_METEO.value,
    })

    # Fill solar radiation NaNs (e.g. night hours where API might return 0 or None)
    df["solar_radiation_wm2"] = df["solar_radiation_wm2"].fillna(0.0).clip(lower=0.0)

    # Validate against core schema
    return validate_weather_dataframe(df)
