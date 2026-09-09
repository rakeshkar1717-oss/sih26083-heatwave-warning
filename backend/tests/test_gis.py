"""Unit tests for GIS Boundary Loader and Spatial Join with fallback logic."""

from pathlib import Path
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from backend.gis import load_ward_boundaries, join_weather_to_wards


@pytest.fixture
def sample_wards_geojson(tmp_path):
    """Generate temporary GeoJSON fixture with 2 fake ward polygons."""
    geojson_path = tmp_path / "test_wards.geojson"
    # Ward 1: [0, 0] to [1, 1]
    poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    # Ward 2: [1, 0] to [2, 1]
    poly2 = Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)])

    gdf = gpd.GeoDataFrame({
        "admin_code": ["W_01", "W_02"],
        "admin_name": ["Alpha Ward", "Beta Ward"],
        "geometry": [poly1, poly2]
    }, crs="EPSG:4326")

    gdf.to_file(geojson_path, driver="GeoJSON")
    return geojson_path


def test_load_ward_boundaries_success(sample_wards_geojson):
    """Ensure boundary loader standardizes column names and validates CRS."""
    gdf = load_ward_boundaries(sample_wards_geojson)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_string() == "EPSG:4326"
    assert "ward_id" in gdf.columns
    assert "ward_name" in gdf.columns
    assert len(gdf) == 2
    assert gdf["ward_id"].iloc[0] == "W_01"


def test_load_ward_boundaries_missing_file():
    """Ensure FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        load_ward_boundaries("non_existent_wards.geojson")


def test_join_weather_to_wards_within_polygon(sample_wards_geojson):
    """Ensure points strictly within a ward polygon are correctly matched."""
    wards_gdf = load_ward_boundaries(sample_wards_geojson)

    weather_df = pd.DataFrame({
        "lat": [0.5, 0.7],
        "lon": [0.5, 1.5],
        "temp_c": [35.0, 38.0],
        "source": ["open_meteo", "open_meteo"],
    })

    joined = join_weather_to_wards(weather_df, wards_gdf)
    assert len(joined) == 2
    assert joined.loc[0, "ward_id"] == "W_01"
    assert joined.loc[0, "ward_name"] == "Alpha Ward"
    assert joined.loc[1, "ward_id"] == "W_02"
    assert joined.loc[1, "ward_name"] == "Beta Ward"


def test_join_weather_to_wards_nearest_fallback(sample_wards_geojson, caplog):
    """Ensure points outside polygons trigger nearest fallback and log warning."""
    wards_gdf = load_ward_boundaries(sample_wards_geojson)

    # Point at (lon 2.5, lat 0.5) is outside both wards, closest to Ward 2
    weather_df = pd.DataFrame({
        "lat": [0.5],
        "lon": [2.5],
        "temp_c": [36.0],
        "source": ["open_meteo"],
    })

    with caplog.at_level("WARNING"):
        joined = join_weather_to_wards(weather_df, wards_gdf)

    assert len(joined) == 1
    # Must be assigned to nearest ward (W_02)
    assert joined.loc[0, "ward_id"] == "W_02"
    assert "fell outside municipal ward polygon boundaries" in caplog.text
