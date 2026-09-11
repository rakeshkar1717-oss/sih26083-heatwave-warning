"""Data ingestion package for meteorological observations and reanalysis data."""

from backend.data_ingestion.ingest import get_weather_data
from backend.data_ingestion import open_meteo, nasa_power, era5, fusion, bias_correction
from backend.data_ingestion.fusion import fuse_sources, fuse_weather_sources, fetch_fused_weather
from backend.data_ingestion.bias_correction import apply_bias_correction, compute_source_biases

__all__ = [
    "get_weather_data",
    "open_meteo",
    "nasa_power",
    "era5",
    "fusion",
    "bias_correction",
    "fuse_sources",
    "fuse_weather_sources",
    "fetch_fused_weather",
    "apply_bias_correction",
    "compute_source_biases",
]

