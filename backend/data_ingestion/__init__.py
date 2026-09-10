"""Data ingestion package for meteorological observations and reanalysis data."""

from backend.data_ingestion.ingest import get_weather_data
from backend.data_ingestion import open_meteo, nasa_power, era5
from backend.data_ingestion.data_fusion import fuse_weather_sources, fetch_fused_weather

__all__ = [
    "get_weather_data",
    "open_meteo",
    "nasa_power",
    "era5",
    "fuse_weather_sources",
    "fetch_fused_weather",
]

