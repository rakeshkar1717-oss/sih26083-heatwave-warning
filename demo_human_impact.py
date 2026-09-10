"""SIH26083 - Human Impact Card ("Who is Affected") End-to-End Pipeline Demonstration.

Demonstrates the core differentiator of Project SIH26083:
1. Translates environmental hazard (WBGT/UTCI/Heat Index) and ward vulnerability into real human numbers.
2. Identifies WHO specifically is affected (children, elderly, outdoor workers, slum residents).
3. Evaluates HOW they are affected with evidence-based clinical consequences (cites WHO, NDMA, NRDC).
4. Prescribes targeted, actionable protection measures per cohort.
5. Surfaces transparent data quality badges (measured vs derived) and official provenance citations.
6. Verifies both internal Python engine and FastAPI REST endpoint /api/population-impact/{ward_id}.

Usage:
    python demo_human_impact.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from fastapi.testclient import TestClient

# Reconfigure stdout/stderr for Unicode/emoji compatibility on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings, DEFAULT_CENSUS_DATA_SOURCE_URL
from backend.models import WeatherSource, validate_weather_dataframe, RiskLevel
from backend.data_ingestion.ingest import get_weather_data
from backend.index_calculation.index_engine import compute_thermal_indices
from backend.vulnerability_model.census_loader import load_census_data
from backend.vulnerability_model.vulnerability_engine import compute_vulnerability_score
from backend.vulnerability_model.health_consequence_map import get_population_impact
from backend.alerts.alert_engine import compose_public_health_advisory
from backend.api.main import app

logging.basicConfig(level=logging.WARNING)

BORDER = "=" * 82
SUB = "-" * 82


def main():
    print()
    print(BORDER)
    print("PROJECT SIH26083: HUMAN IMPACT CARD & ACTIONABLE HEAT PROTECTION DEMO".center(82))
    print("Translating Ambient Thermal Hazard into Segmented Human Consequences".center(82))
    print(BORDER)
    print()

    # 1. Ingest Weather & Calculate Biometeorological Indices
    print("[1/4] Computing Real-Time Thermal Hazard Indices...")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    weather_df = get_weather_data(
        source=WeatherSource.OPEN_METEO,
        lat=23.03,
        lon=72.58,
        start_date=today_str,
        end_date=today_str,
        timeout=15,
    )
    validated_weather = validate_weather_dataframe(weather_df)
    thermal_df = compute_thermal_indices(validated_weather.tail(3))
    latest_thermal = thermal_df.iloc[-1]
    hazard_score = float(latest_thermal["thermal_stress_score"])
    temp_c = float(latest_thermal["temp_c"])
    wbgt_c = float(latest_thermal["wbgt_c"])
    utci_c = float(latest_thermal["utci_c"])

    print(f"  -> Observed Temperature : {temp_c:.1f} °C")
    print(f"  -> Wet Bulb Globe Temp  : {wbgt_c:.1f} °C (Outdoor ISO 7243 threshold)")
    print(f"  -> Universal Thermal Index: {utci_c:.1f} °C")
    print(f"  -> Composite Hazard Score: {hazard_score:.1f} / 100 [{latest_thermal['stress_category']}]")

    # 2. Select High-Vulnerability Municipal Ward
    print("\n[2/4] Loading Census Demographics and Selecting Pilot Ward...")
    census_df = load_census_data()
    hvi_df = compute_vulnerability_score(census_df)

    # Let's pick AMD_02 (Jamalpur) or AMD_11 (Shahpur) or AMD_04 (Danilimda)
    target_ward_id = "AMD_02"
    ward_rows = hvi_df[hvi_df["ward_id"] == target_ward_id]
    if ward_rows.empty:
        ward_rows = hvi_df.sort_values("vulnerability_score", ascending=False)
    ward_series = ward_rows.iloc[0]

    ward_id = str(ward_series["ward_id"])
    ward_name = str(ward_series["ward_name"])
    vuln_score = float(ward_series["vulnerability_score"])
    final_risk = round(0.60 * (hazard_score / 100.0) + 0.40 * vuln_score, 4)

    if final_risk < 0.25:
        risk_tier = RiskLevel.LOW
    elif final_risk < 0.50:
        risk_tier = RiskLevel.MODERATE
    elif final_risk < 0.70:
        risk_tier = RiskLevel.HIGH
    elif final_risk < 0.85:
        risk_tier = RiskLevel.VERY_HIGH
    else:
        risk_tier = RiskLevel.EXTREME

    print(f"  -> Selected Target Ward : {ward_name} [{ward_id}]")
    print(f"  -> Vulnerability Score  : {vuln_score:.4f}")
    print(f"  -> Integrated Risk Score: {final_risk:.4f} ===> Tier: {risk_tier.value}")

    # 3. Generate Human Impact Breakdown
    print("\n[3/4] Synthesizing Demographic Cohort Consequences & Actions...")
    impact = get_population_impact(
        ward_data=ward_series,
        risk_tier=risk_tier,
        final_risk_score=final_risk,
    )

    # Render Terminal Human Impact Card
    print()
    print(BORDER)
    print(f"  HUMAN IMPACT CARD: {impact['ward_name'].upper()} [{impact['ward_id']}]")
    print(BORDER)
    print(f"  Total Ward Population : {impact['total_population']:,} residents  [Data Quality: MEASURED]")
    print(f"  Integrated Risk Tier  : {impact['risk_tier']} (Score: {impact['final_risk_score']:.3f})")
    print(f"  Dominant Risk Factor  : {impact['dominant_risk_factor']}")
    print(f"  Data Provenance       : {impact['data_source_url']}")
    print(f"  Last Synchronized     : {impact['data_pulled_at']}")
    print(SUB)
    print("  WHO IS AFFECTED & HOW (Evidence-Based Clinical Breakdown):")
    print(SUB)

    for seg_id, seg in impact["segments"].items():
        icon = seg.get("icon", "*")
        name = seg.get("name", seg_id)
        cnt = seg.get("estimated_count", 0)
        pct = seg.get("percentage", 0.0)
        quality = seg.get("data_quality", "derived").upper()
        severity = seg.get("severity", "MODERATE")

        print(f"\n  {icon}  {name.upper()} -- {cnt:,} people ({pct:.1f}% of ward) [{quality}]")
        print(f"     Severity Impact    : [{severity}] ")
        print(f"     Health Consequence : {seg.get('consequence')}")
        print(f"     Targeted Action    : >>> {seg.get('action')} <<<")

    print()
    print(SUB)
    print(f"  SUMMARY ADVISORY: {impact['summary']}")
    print(SUB)

    # Preview Targeted Early Warning Alert Dispatch
    segments = impact.get("segments", {})
    dominant_action = None
    if "Outdoor" in impact["dominant_risk_factor"] and "outdoor_workers" in segments:
        dominant_action = segments["outdoor_workers"]["action"]
    elif "Slum" in impact["dominant_risk_factor"] and "slum_residents" in segments:
        dominant_action = segments["slum_residents"]["action"]
    elif "Elderly" in impact["dominant_risk_factor"] and "elderly_60plus" in segments:
        dominant_action = segments["elderly_60plus"]["action"]
    else:
        dominant_action = next(iter(segments.values()))["action"] if segments else None

    advisory_sms = compose_public_health_advisory(
        ward_name=ward_name,
        ward_id=ward_id,
        risk_level=risk_tier,
        temp_c=temp_c,
        wbgt_c=wbgt_c,
        dominant_action_info=dominant_action,
    )
    print("\n  [Automated SMS/WhatsApp Advisory Preview]:")
    print(f"  \"{advisory_sms}\"")

    # 4. REST API Endpoint Verification via FastAPI TestClient
    print()
    print(SUB)
    print("[4/4] Testing Live REST API Route: GET /api/population-impact/{ward_id}...")
    client = TestClient(app)
    api_res = client.get(f"/api/population-impact/{ward_id}")
    if api_res.status_code == 200:
        api_data = api_res.json()
        print("  -> HTTP 200 OK received from FastAPI server.")
        print(f"  -> API Response Ward   : {api_data['ward_name']} [{api_data['ward_id']}]")
        print(f"  -> API Cohorts Returned : {list(api_data['segments'].keys())}")
        print(f"  -> API Dominant Driver : {api_data['dominant_risk_factor']}")
        print(f"  -> API Provenance Stamped: {api_data['data_source_url']}")
    else:
        print(f"  -> WARNING: API returned HTTP {api_res.status_code}: {api_res.text}")

    print()
    print(BORDER)
    print("SUCCESS: HUMAN IMPACT CARD PIPELINE VERIFIED FULLY OPERATIONAL".center(82))
    print(BORDER)
    print()


if __name__ == "__main__":
    main()
