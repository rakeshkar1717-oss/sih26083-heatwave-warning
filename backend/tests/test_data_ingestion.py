"""Unit and Mock Tests for Day 1 Weather Data Ingestion Pipeline."""

from datetime import datetime, timezone
import pandas as pd
import pytest
import requests

from backend.data_ingestion import get_weather_data, open_meteo, nasa_power, era5
from backend.models import (
    FIXED_WEATHER_COLUMNS,
    WeatherSource,
    validate_weather_dataframe,
)


# ==============================================================================
# 1. Schema Validation Tests
# ==============================================================================

def test_validate_weather_dataframe_valid():
    """Ensure a conforming DataFrame passes validation without error."""
    sample_data = {
        "timestamp": [datetime.now(timezone.utc)],
        "lat": [23.03],
        "lon": [72.58],
        "temp_c": [38.2],
        "humidity_pct": [42.0],
        "wind_speed_ms": [3.5],
        "solar_radiation_wm2": [650.0],
        "source": [WeatherSource.OPEN_METEO.value],
    }
    df = pd.DataFrame(sample_data)
    validated = validate_weather_dataframe(df)
    assert list(validated.columns) == FIXED_WEATHER_COLUMNS
    assert len(validated) == 1


def test_validate_weather_dataframe_missing_col():
    """Ensure missing columns raise ValueError."""
    bad_df = pd.DataFrame({
        "timestamp": [datetime.now(timezone.utc)],
        "lat": [23.03],
        "temp_c": [38.2],
    })
    with pytest.raises(ValueError, match="missing required column"):
        validate_weather_dataframe(bad_df)


def test_validate_weather_dataframe_invalid_source():
    """Ensure unknown sources raise ValueError."""
    bad_df = pd.DataFrame({
        "timestamp": [datetime.now(timezone.utc)],
        "lat": [23.03],
        "lon": [72.58],
        "temp_c": [38.2],
        "humidity_pct": [42.0],
        "wind_speed_ms": [3.5],
        "solar_radiation_wm2": [650.0],
        "source": ["unsupported_provider"],
    })
    with pytest.raises(ValueError, match="Invalid weather source"):
        validate_weather_dataframe(bad_df)


# ==============================================================================
# 2. Open-Meteo Ingestion Tests (Mocked)
# ==============================================================================

def test_open_meteo_fetch_mocked(monkeypatch):
    """Test Open-Meteo fetcher with mocked HTTP response."""
    mock_payload = {
        "hourly": {
            "time": ["2026-09-01T00:00", "2026-09-01T01:00"],
            "temperature_2m": [30.5, 29.8],
            "relative_humidity_2m": [55.0, 58.0],
            "wind_speed_10m": [2.4, 2.1],
            "shortwave_radiation_instant": [0.0, 0.0],
        }
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return mock_payload
        def raise_for_status(self):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests.Session, "get", mock_get)

    df = open_meteo.fetch(23.03, 72.58, "2026-09-01", "2026-09-01")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == FIXED_WEATHER_COLUMNS
    assert len(df) == 2
    assert df["source"].iloc[0] == WeatherSource.OPEN_METEO.value
    assert df["temp_c"].iloc[0] == 30.5


# ==============================================================================
# 3. NASA POWER Ingestion Tests (Mocked)
# ==============================================================================

def test_nasa_power_fetch_mocked(monkeypatch):
    """Test NASA POWER fetcher with mocked HTTP response."""
    mock_payload = {
        "properties": {
            "parameter": {
                "T2M": {"2024050100": 28.5, "2024050101": 27.8},
                "RH2M": {"2024050100": 60.0, "2024050101": 63.0},
                "WS10M": {"2024050100": 3.1, "2024050101": 2.9},
                "ALLSKY_SFC_SW_DWN": {"2024050100": -999.0, "2024050101": 0.0},
            }
        }
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return mock_payload
        def raise_for_status(self):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests.Session, "get", mock_get)

    df = nasa_power.fetch(23.03, 72.58, "2024-05-01", "2024-05-01")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == FIXED_WEATHER_COLUMNS
    assert len(df) == 2
    assert df["source"].iloc[0] == WeatherSource.NASA_POWER.value
    # Assert missing solar radiation -999 was converted to 0.0
    assert df["solar_radiation_wm2"].iloc[0] == 0.0


# ==============================================================================
# 4. ERA5 Error Handling & Ingestion Tests
# ==============================================================================

def test_era5_missing_key_raises(monkeypatch):
    """Ensure ERA5 raises clear error when CDS credentials are not configured."""
    from backend.config import settings
    monkeypatch.setattr(settings, "cds_api_key", None)
    monkeypatch.delenv("CDS_API_KEY", raising=False)
    monkeypatch.delenv("CDSAPI_KEY", raising=False)

    with pytest.raises(RuntimeError, match="CDS_API_KEY is not set"):
        era5.fetch(23.03, 72.58, "2023-05-01", "2023-05-02")


def test_era5_with_mock_client(monkeypatch):
    """Ensure ERA5 correctly formats data when client is provided or mocked."""
    from backend.config import settings
    monkeypatch.setattr(settings, "cds_api_key", "mock-token-xyz")

    sample_df = pd.DataFrame({
        "timestamp": [pd.to_datetime("2023-05-01 00:00:00+00:00")],
        "lat": [23.03],
        "lon": [72.58],
        "temp_c": [32.0],
        "humidity_pct": [50.0],
        "wind_speed_ms": [2.5],
        "solar_radiation_wm2": [100.0],
        "source": [WeatherSource.ERA5.value],
    })

    class MockCDSClient:
        def retrieve(self, dataset, params):
            return sample_df

    res_df = era5.fetch(23.03, 72.58, "2023-05-01", "2023-05-01", client=MockCDSClient())
    assert list(res_df.columns) == FIXED_WEATHER_COLUMNS
    assert res_df["source"].iloc[0] == WeatherSource.ERA5.value


# ==============================================================================
# 5. Unified Ingest Router Tests
# ==============================================================================

def test_get_weather_data_invalid_coords():
    """Ensure out-of-range coordinates are caught early."""
    with pytest.raises(ValueError, match="Latitude 120\\.0 out of range"):
        get_weather_data("open_meteo", 120.0, 72.58, "2026-09-01", "2026-09-02")

    with pytest.raises(ValueError, match="Longitude -200\\.0 out of range"):
        get_weather_data("open_meteo", 23.03, -200.0, "2026-09-01", "2026-09-02")


def test_get_weather_data_invalid_source():
    """Ensure unsupported provider names are rejected."""
    with pytest.raises(ValueError, match="Unsupported weather source"):
        get_weather_data("unknown_sat", 23.03, 72.58, "2026-09-01", "2026-09-02")


def test_get_weather_data_routes_properly(monkeypatch):
    """Ensure get_weather_data routes correctly and outputs valid schema."""
    def mock_fetch(lat, lon, start, end, **kwargs):
        return pd.DataFrame({
            "timestamp": [pd.to_datetime("2026-09-01 00:00:00+00:00")],
            "lat": [lat],
            "lon": [lon],
            "temp_c": [35.0],
            "humidity_pct": [40.0],
            "wind_speed_ms": [3.0],
            "solar_radiation_wm2": [500.0],
            "source": [WeatherSource.OPEN_METEO.value],
        })

    monkeypatch.setattr(open_meteo, "fetch", mock_fetch)

    df = get_weather_data(WeatherSource.OPEN_METEO, 23.03, 72.58, "2026-09-01", "2026-09-01")
    assert list(df.columns) == FIXED_WEATHER_COLUMNS
    assert len(df) == 1
    assert df["temp_c"].iloc[0] == 35.0
