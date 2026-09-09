"""Tests for Historical Backtesting & Scientific Validation Subsystem (Day 8).

Verifies historical weather puller caching, pipeline execution against sample fixtures,
validation reporting, and REST API endpoints.
"""

from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.config import BASE_DIR, BACKTEST_EVENT
from backend.models import validate_weather_dataframe
from backend.backtesting.historical_puller import pull_historical_weather
from backend.backtesting.validation_report import (
    run_backtest_pipeline,
    generate_validation_report,
)
from backend.api.main import app

FIXTURES_DIR = BASE_DIR / "backend" / "tests" / "fixtures"
SAMPLE_FIXTURE_PATH = FIXTURES_DIR / "historical_weather_sample.csv"


@pytest.fixture
def sample_weather_df() -> pd.DataFrame:
    """Load cached 48-hour historical sample fixture."""
    if not SAMPLE_FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file {SAMPLE_FIXTURE_PATH} not found.")
    df = pd.read_csv(SAMPLE_FIXTURE_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return validate_weather_dataframe(df)


def test_pull_historical_weather_uses_cache(monkeypatch):
    """Confirm historical puller loads from local cache without external network queries."""
    cache_file = BASE_DIR / "data" / "cache" / "historical_ahmedabad_may2010.csv"
    if not cache_file.exists():
        pytest.skip(f"Historical cache file {cache_file} not present.")

    # Guard against accidental HTTP queries
    def fail_requests_get(*args, **kwargs):
        raise RuntimeError("External network request attempted in unit test!")

    monkeypatch.setattr("requests.Session.get", fail_requests_get)

    df = pull_historical_weather(
        city="Ahmedabad",
        start_date="2010-05-15",
        end_date="2010-05-27",
        use_cache=True,
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "temp_c" in df.columns
    assert "humidity_pct" in df.columns
    assert df["source"].iloc[0] == "era5"


def test_historical_weather_sample_fixture_conforms(sample_weather_df):
    """Verify that sample historical fixture satisfies all canonical weather column requirements."""
    assert len(sample_weather_df) == 48
    assert sample_weather_df["temp_c"].max() >= 40.0
    assert sample_weather_df["source"].iloc[0] == "era5"


def test_run_backtest_pipeline_with_fixture(sample_weather_df):
    """Verify full scientific pipeline execution on historical test fixture."""
    results = run_backtest_pipeline(weather_df=sample_weather_df)

    assert "daily_df" in results
    assert "ward_risk_df" in results
    assert "peak_summary" in results
    assert "event_metadata" in results

    daily_df = results["daily_df"]
    assert len(daily_df) > 0
    assert "max_temp_c" in daily_df.columns
    assert "max_thermal_stress" in daily_df.columns

    ward_risk_df = results["ward_risk_df"]
    assert len(ward_risk_df) == 48
    assert "final_risk_score" in ward_risk_df.columns
    assert "risk_level" in ward_risk_df.columns

    # Peak hazard check
    peak_row = results["peak_summary"]
    assert peak_row["max_temp_c"] >= 40.0


def test_generate_validation_report_execution(tmp_path, sample_weather_df):
    """Verify validation report generation writes markdown and cites Azhar et al."""
    out = generate_validation_report(
        output_dir=tmp_path,
        make_plot=False,  # Skip plot in headless test
        weather_df=sample_weather_df,
    )

    assert "report_file" in out
    report_path = Path(out["report_file"])
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")
    assert "Azhar GS, et al. (2014)" in content
    assert "Ahmedabad May 2010" in content
    assert "Outdoor WBGT" in content


def test_backtest_api_endpoints():
    """Verify /api/backtest/* REST API endpoints return 200 OK and valid JSON structures."""
    client = TestClient(app)

    # 1. Summary endpoint
    res_sum = client.get("/api/backtest/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert sum_data["city"] == "Ahmedabad"
    assert "Azhar" in sum_data["source_citation"]
    assert sum_data["peak_temp_c"] >= 40.0

    # 2. Timeline endpoint
    res_time = client.get("/api/backtest/timeline")
    assert res_time.status_code == 200
    time_data = res_time.json()
    assert "timeline" in time_data
    assert len(time_data["timeline"]) > 0

    # 3. GeoJSON endpoint
    res_geo = client.get("/api/backtest/geojson")
    assert res_geo.status_code == 200
    geo_data = res_geo.json()
    assert geo_data["type"] == "FeatureCollection"
    assert geo_data["is_backtest_mode"] is True
    assert len(geo_data["features"]) == 48

    # Verify first feature properties
    props = geo_data["features"][0]["properties"]
    assert props["is_historical_backtest"] is True
    assert "temp_c" in props
    assert "thermal_stress_score" in props
    assert "final_risk_score" in props
