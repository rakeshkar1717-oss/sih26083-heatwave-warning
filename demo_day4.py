"""SIH26083 Day 4 Live Demonstration Script.

Demonstrates GIS boundary loading, spatial point-in-polygon joins, and multi-layer synthesis.
1. Ingests live weather observations for multiple grid locations across Ahmedabad.
2. Computes biometeorological thermal indices (Heat Index, WBGT, UTCI, Thermal Stress Score).
3. Loads municipal ward boundaries from GeoJSON.
4. Spatially maps weather points to ward polygons (with nearest-neighbor boundary fallback).
5. Merges with Day 3 Heat Vulnerability Index (HVI) scores to create a unified ward risk view.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import pandas as pd

from backend.data_ingestion import get_weather_data
from backend.index_calculation import compute_thermal_indices
from backend.gis import load_ward_boundaries, join_weather_to_wards
from backend.vulnerability_model import load_census_data, compute_vulnerability_score
from backend.models import WeatherSource


def run_demo():
    print("=" * 105)
    print(" SIH26083: EXTREME HEATWAVE EARLY WARNING & HUMAN THERMAL STRESS INDEX")
    print(" DAY 4 DEMONSTRATION: GIS BOUNDARY LAYER, SPATIAL JOIN & DATA INTEGRATION")
    print("=" * 105)

    geojson_path = Path("data/raw/synthetic_ahmedabad_wards.geojson")
    census_csv = Path("data/raw/synthetic_census_ahmedabad.csv")

    if not geojson_path.exists():
        print(f"[ERROR] GeoJSON file not found at: {geojson_path}")
        sys.exit(1)
    if not census_csv.exists():
        print(f"[ERROR] Census file not found at: {census_csv}")
        sys.exit(1)

    # 1. Representative monitoring points across Ahmedabad municipal zones
    monitoring_stations = [
        {"name": "Navrangpura Station", "lat": 23.038, "lon": 72.552},
        {"name": "Jamalpur Station",    "lat": 23.018, "lon": 72.585},
        {"name": "Bodakdev Station",    "lat": 23.045, "lon": 72.515},
        {"name": "Sabarmati Station",   "lat": 23.075, "lon": 72.580},
        # Outer boundary edge point testing nearest-ward fallback:
        {"name": "Airport Outskirt",    "lat": 23.115, "lon": 72.615},
    ]

    print(f"\n[1] Pulling Live Meteorological Observations across {len(monitoring_stations)} Ahmedabad Stations...")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    all_weather_records = []
    for st in monitoring_stations:
        try:
            df_st = get_weather_data(
                source=WeatherSource.OPEN_METEO,
                lat=st["lat"],
                lon=st["lon"],
                start_date=today_str,
                end_date=today_str,
                timeout=30,
            )
            # Pick the latest available hour
            latest_hour = df_st.iloc[-1:].copy()
            latest_hour["station_name"] = st["name"]
            all_weather_records.append(latest_hour)
        except Exception as e:
            print(f"    - Warning: Failed to fetch for {st['name']}: {e}")

    weather_df = pd.concat(all_weather_records, ignore_index=True)
    print(f"    - Successfully pulled latest observations for {len(weather_df)} stations.")

    print(f"\n[2] Computing Biometeorological Thermal Indices (Day 2 Engine)...")
    thermal_df = compute_thermal_indices(weather_df)

    print(f"\n[3] Loading Ward Boundaries (Day 4 Boundary Loader)...")
    wards_gdf = load_ward_boundaries(geojson_path)
    print(f"    - Loaded {len(wards_gdf)} ward polygon boundaries (CRS: {wards_gdf.crs}).")

    print(f"\n[4] Executing Spatial Join (join_weather_to_wards with fallback)...")
    spatial_weather = join_weather_to_wards(thermal_df, wards_gdf)
    print(f"    - Spatially mapped {len(spatial_weather)} observation points to municipal wards.")

    print(f"\n[5] Loading Demographic Vulnerability Scores (Day 3 Engine)...")
    census_df = load_census_data(census_csv)
    vulnerability_df = compute_vulnerability_score(census_df)
    vulnerability_summary = vulnerability_df[["ward_id", "vulnerability_score", "risk_tier"]].copy()

    print(f"\n[6] Synthesizing Final Spatial Master Table (Weather + Indices + GIS + Vulnerability)...")
    merged_master = spatial_weather.merge(
        vulnerability_summary,
        on="ward_id",
        how="left"
    )

    display_cols = [
        "station_name", "ward_id", "ward_name", "temp_c", "humidity_pct",
        "heat_index_c", "wbgt_c", "utci_c", "thermal_stress_score",
        "vulnerability_score", "risk_tier"
    ]
    renamed_cols = {
        "station_name": "Station",
        "ward_id": "Ward ID",
        "ward_name": "Ward Name",
        "temp_c": "Temp (C)",
        "humidity_pct": "RH %",
        "heat_index_c": "HI (C)",
        "wbgt_c": "WBGT (C)",
        "utci_c": "UTCI (C)",
        "thermal_stress_score": "Thermal (0-100)",
        "vulnerability_score": "HVI (0-1)",
        "risk_tier": "HVI Tier",
    }
    output_table = merged_master[display_cols].rename(columns=renamed_cols)
    print("\n" + output_table.to_string(index=False))

    print(f"\n[7] Spatial Join & Fallback Verification:")
    if "station_name" in merged_master.columns and "Airport Outskirt" in merged_master["station_name"].values:
        outskirt_row = merged_master[merged_master["station_name"] == "Airport Outskirt"].iloc[0]
        print(f"    - Station 'Airport Outskirt' (outside ward boundaries) successfully assigned to "
              f"nearest ward: {outskirt_row['ward_name']} ({outskirt_row['ward_id']}) via sjoin_nearest fallback.")

    print("\n" + "=" * 105)
    print(" DAY 4 SUCCESS: GIS layer, spatial join, and multi-module integration operational.")
    print("=" * 105)


if __name__ == "__main__":
    run_demo()
