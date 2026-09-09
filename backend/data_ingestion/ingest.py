"""Unified weather data ingestion interface for SIH26083.

Provides a single entry point `get_weather_data(...)` that routes queries to the
appropriate meteorological provider (Open-Meteo, NASA POWER, or ERA5) and strictly
validates the output against the shared data schema in `backend.models`.
"""

import logging
from typing import Union
import pandas as pd

from backend.models import (
    FIXED_WEATHER_COLUMNS,
    WeatherSource,
    validate_weather_dataframe,
)
from backend.data_ingestion import open_meteo, nasa_power, era5

logger = logging.getLogger(__name__)


def get_weather_data(
    source: Union[str, WeatherSource],
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    **kwargs
) -> pd.DataFrame:
    """Unified entry point for ingesting weather data across all supported providers.

    Parameters
    ----------
    source : Union[str, WeatherSource]
        Provider identifier: 'open_meteo', 'nasa_power', or 'era5'.
    lat : float
        Latitude in decimal degrees (-90.0 to 90.0).
    lon : float
        Longitude in decimal degrees (-180.0 to 180.0).
    start_date : str
        Start date string ('YYYY-MM-DD' or 'YYYYMMDD').
    end_date : str
        End date string ('YYYY-MM-DD' or 'YYYYMMDD').
    **kwargs : Any
        Optional provider-specific arguments (e.g. timeout, session, cds_client).

    Returns
    -------
    pd.DataFrame
        Validated pandas DataFrame strictly adhering to the schema:
        [timestamp, lat, lon, temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2, source]

    Raises
    ------
    ValueError
        If an unsupported provider is requested, coordinates are out of bounds,
        or the returned dataset fails schema validation.
    RuntimeError
        If required credentials for a provider are missing (e.g. ERA5 CDS key).
    """
    # 1. Validate coordinates
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude {lat} out of range [-90.0, 90.0]")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitude {lon} out of range [-180.0, 180.0]")

    # 2. Normalize and validate provider
    if isinstance(source, WeatherSource):
        source_key = source.value
    elif isinstance(source, str):
        source_key = source.strip().lower()
    else:
        raise ValueError(f"Invalid source type '{type(source)}'. Expected str or WeatherSource.")

    valid_sources = [s.value for s in WeatherSource]
    if source_key not in valid_sources:
        raise ValueError(
            f"Unsupported weather source: '{source}'. "
            f"Supported sources are: {valid_sources}"
        )

    logger.info(
        "Routing weather ingestion to '%s' for (%.4f, %.4f) from %s to %s",
        source_key, lat, lon, start_date, end_date
    )

    # 3. Route to respective provider
    if source_key == WeatherSource.OPEN_METEO.value:
        raw_df = open_meteo.fetch(lat, lon, start_date, end_date, **kwargs)
    elif source_key == WeatherSource.NASA_POWER.value:
        raw_df = nasa_power.fetch(lat, lon, start_date, end_date, **kwargs)
    elif source_key == WeatherSource.ERA5.value:
        raw_df = era5.fetch(lat, lon, start_date, end_date, **kwargs)
    else:
        raise ValueError(f"Provider '{source_key}' routing not implemented.")

    # 4. Strictly validate schema and column contracts
    validated_df = validate_weather_dataframe(raw_df)

    logger.info(
        "Successfully ingested and validated %d records from '%s'",
        len(validated_df), source_key
    )
    return validated_df
