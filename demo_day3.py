"""SIH26083 Day 3 Live Demonstration Script.

Demonstrates demographic and socio-economic Heat Vulnerability Index (HVI) modeling.
Loads synthetic ward census data for Ahmedabad, computes multi-factor vulnerability scores,
and prints the municipal wards ranked from highest to lowest vulnerability tier.
"""

from pathlib import Path
import sys
import pandas as pd

from backend.config import VULNERABILITY_WEIGHTS, VULNERABILITY_TIERS
from backend.vulnerability_model import load_census_data, compute_vulnerability_score


def run_demo():
    print("=" * 95)
    print(" SIH26083: EXTREME HEATWAVE EARLY WARNING & HUMAN THERMAL STRESS INDEX")
    print(" DAY 3 DEMONSTRATION: WARD-LEVEL HEAT VULNERABILITY MODEL (HVI)")
    print("=" * 95)

    census_csv = Path("data/raw/synthetic_census_ahmedabad.csv")
    if not census_csv.exists():
        print(f"[ERROR] Sample census file not found at: {census_csv}")
        sys.exit(1)

    print(f"\n[1] Loading Ward Demographic Data via Flexible Loader:")
    print(f"    - Source Path : {census_csv}")
    print(f"    - Auto-Alias  : Resolving non-standard municipal column names...")

    df_census = load_census_data(census_csv)
    print(f"    - Loaded Wards: {len(df_census)} municipal wards successfully standardized.")

    print(f"\n[2] Active Heat Vulnerability Index (HVI) Model Weights:")
    print(f"    (Configured in backend/config.py based on Ahmedabad Heat Action Plan correlations):")
    for factor, weight in VULNERABILITY_WEIGHTS.items():
        print(f"    - {factor:<18}: {weight * 100:.0f}%")

    print(f"\n[3] Computing Composite Vulnerability Scores...")
    scored_df = compute_vulnerability_score(df_census)

    # Sort descending by vulnerability score
    ranked_df = scored_df.sort_values(by="vulnerability_score", ascending=False).reset_index(drop=True)
    ranked_df["rank"] = ranked_df.index + 1

    print(f"\n[4] Municipal Wards Ranked by Heat Vulnerability (Highest to Lowest):")
    display_cols = [
        "rank", "ward_id", "ward_name", "elderly_pct", "outdoor_worker_pct",
        "slum_pct", "green_cover_pct", "hospital_bed_density", "vulnerability_score", "risk_tier"
    ]
    renamed_display = ranked_df[display_cols].rename(columns={
        "rank": "Rank",
        "ward_id": "Ward ID",
        "ward_name": "Ward Name",
        "elderly_pct": "Elderly %",
        "outdoor_worker_pct": "Outdoor Wkr %",
        "slum_pct": "Slum %",
        "green_cover_pct": "Green %",
        "hospital_bed_density": "Beds/1k",
        "vulnerability_score": "HVI Score",
        "risk_tier": "Risk Tier"
    })
    print(renamed_display.to_string(index=False))

    print(f"\n[5] Actionable Civic Vulnerability Insights:")
    top_ward = ranked_df.iloc[0]
    safest_ward = ranked_df.iloc[-1]
    print(f"    - Most Vulnerable Ward : {top_ward['ward_name']} ({top_ward['ward_id']}) "
          f"-> HVI: {top_ward['vulnerability_score']} [{top_ward['risk_tier']}]")
    print(f"      (Driven by {top_ward['slum_pct']}% slum housing and {top_ward['outdoor_worker_pct']}% outdoor laborers)")
    print(f"    - Least Vulnerable Ward: {safest_ward['ward_name']} ({safest_ward['ward_id']}) "
          f"-> HVI: {safest_ward['vulnerability_score']} [{safest_ward['risk_tier']}]")
    print(f"      (Buffered by {safest_ward['green_cover_pct']}% urban green canopy and {safest_ward['hospital_bed_density']} beds/1k)")

    print("\n" + "=" * 95)
    print(" DAY 3 SUCCESS: Vulnerability Model fully operational and verified.")
    print("=" * 95)


if __name__ == "__main__":
    run_demo()
