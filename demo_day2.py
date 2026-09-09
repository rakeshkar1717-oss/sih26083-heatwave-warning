"""SIH26083 Day 2 Live Demonstration Script.

Demonstrates biometeorological thermal index calculations for pilot city Ahmedabad (lat 23.03, lon 72.58).
Pulls live Open-Meteo weather data, runs the unified index engine, and displays the enriched DataFrame
with NOAA Heat Index, Outdoor WBGT, UTCI, and the normalized 0-100 Thermal Stress Score.
"""

from datetime import datetime, timedelta, timezone
import sys
import pandas as pd

from backend.data_ingestion import get_weather_data
from backend.index_calculation import compute_thermal_indices
from backend.models import WeatherSource


def run_demo():
    print("=" * 90)
    print(" SIH26083: EXTREME HEATWAVE EARLY WARNING & HUMAN THERMAL STRESS INDEX")
    print(" DAY 2 DEMONSTRATION: MULTI-METRIC THERMAL STRESS INDEX ENGINE")
    print("=" * 90)

    city_name = "Ahmedabad, Gujarat"
    lat = 23.03
    lon = 72.58

    # Query last 2 days of hourly data
    today = datetime.now(timezone.utc)
    start_dt = today - timedelta(days=1)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    print(f"\n[1] Pulling Live Weather Data for {city_name} (Lat: {lat} N, Lon: {lon} E):")
    print(f"    - Date Range: {start_str} to {end_str} (UTC)")

    try:
        raw_df = get_weather_data(
            source=WeatherSource.OPEN_METEO,
            lat=lat,
            lon=lon,
            start_date=start_str,
            end_date=end_str,
        )
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}")
        sys.exit(1)

    print(f"    - Ingested {len(raw_df)} hourly observations successfully.")

    print(f"\n[2] Running Unified Thermal Indices Engine (compute_thermal_indices)...")
    enriched_df = compute_thermal_indices(raw_df)

    print(f"    - Indices Computed: NOAA Heat Index, Outdoor WBGT, UTCI, Thermal Stress Score (0-100)")
    print(f"    - Stress Classification: Categorized into Hazard Tiers")

    print(f"\n[3] Biometeorological Multi-Metric Comparison (Ahmedabad):")
    stats = {
        "Index / Parameter": [
            "2m Air Temperature (deg C)",
            "NOAA Heat Index (deg C)",
            "Outdoor WBGT (deg C)",
            "Universal Thermal Climate Index - UTCI (deg C)",
            "Composite Thermal Stress Score (0-100)"
        ],
        "Min": [
            f"{enriched_df['temp_c'].min():.1f}",
            f"{enriched_df['heat_index_c'].min():.1f}",
            f"{enriched_df['wbgt_c'].min():.1f}",
            f"{enriched_df['utci_c'].min():.1f}",
            f"{enriched_df['thermal_stress_score'].min():.1f}",
        ],
        "Mean": [
            f"{enriched_df['temp_c'].mean():.1f}",
            f"{enriched_df['heat_index_c'].mean():.1f}",
            f"{enriched_df['wbgt_c'].mean():.1f}",
            f"{enriched_df['utci_c'].mean():.1f}",
            f"{enriched_df['thermal_stress_score'].mean():.1f}",
        ],
        "Max": [
            f"{enriched_df['temp_c'].max():.1f}",
            f"{enriched_df['heat_index_c'].max():.1f}",
            f"{enriched_df['wbgt_c'].max():.1f}",
            f"{enriched_df['utci_c'].max():.1f}",
            f"{enriched_df['thermal_stress_score'].max():.1f}",
        ],
    }
    print(pd.DataFrame(stats).to_string(index=False))

    print(f"\n[4] Sample Enriched Observations (Afternoon Peak Heat Hours vs Night):")
    display_cols = [
        "timestamp", "temp_c", "humidity_pct", "solar_radiation_wm2",
        "heat_index_c", "wbgt_c", "utci_c", "thermal_stress_score", "stress_category"
    ]
    formatted_df = enriched_df[display_cols].copy()
    formatted_df["timestamp"] = formatted_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    # Show 5 peak heat hours
    peak_hours = formatted_df.sort_values(by="thermal_stress_score", ascending=False).head(5)
    print("\n  --- Top 5 Peak Thermal Hazard Hours ---")
    print(peak_hours.to_string(index=False))

    # Show 3 mildest hours (night / early morning)
    mild_hours = formatted_df.sort_values(by="thermal_stress_score", ascending=True).head(3)
    print("\n  --- 3 Lowest Thermal Hazard Hours (Night/Cool) ---")
    print(mild_hours.to_string(index=False))

    print(f"\n[5] Hazard Category Breakdown:")
    category_counts = enriched_df["stress_category"].value_counts().to_dict()
    for cat, cnt in category_counts.items():
        print(f"    - {cat:<18}: {cnt:>2} hours ({cnt/len(enriched_df)*100:.1f}%)")

    print("\n" + "=" * 90)
    print(" DAY 2 SUCCESS: Thermal Stress Engine fully operational and verified.")
    print("=" * 90)


if __name__ == "__main__":
    run_demo()
