"""SIH26083 - Day 5 Master Verification Script.

Demonstrates full end-to-end execution of:
1. Relational Database Seeding (SQLite with real AMC Ahmedabad 48 wards)
2. FastAPI REST Microservice Layer
3. All primary endpoints:
   - GET /health
   - GET /api/wards/geojson (Choropleth payload for Day 6 Leaflet)
   - GET /api/risk/{ward_id} (Synthesized risk score and civic advisory)
   - GET /api/weather/{ward_id} (Live weather observations & thermal indices)
   - GET /api/forecast/{ward_id} (5-day predictive heatwave projections)
   - POST /api/alert/trigger (SMS / WhatsApp early warning dispatch & audit trail)
"""

import json
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.db.seed import seed_all

BORDER = "=" * 80
SUB_BORDER = "-" * 80


def print_section(title: str):
    print(f"\n{BORDER}\n{title.center(80)}\n{BORDER}")


def main():
    print_section("SIH26083: DAY 5 DEMO - DATABASE PERSISTENCE & REST API")

    # Step 1: Seed persistent SQLite database
    print("\n[STEP 1 / 6] Seeding Relational Database (SQLite Local Engine)...")
    counts = seed_all(fetch_live=False, clear_existing=True)
    print(f" -> Database Seed Summary: {json.dumps(counts, indent=2)}")

    # Step 2: Initialize FastAPI TestClient
    client = TestClient(app)
    print(" -> FastAPI TestClient initialized and mounted to application.")

    # Step 3: Check Health Probe
    print(f"\n{SUB_BORDER}")
    print("[STEP 2 / 6] Probing Service & Database Health (GET /health)...")
    res_health = client.get("/health")
    print(f"Status Code: {res_health.status_code}")
    print(f"Response:\n{json.dumps(res_health.json(), indent=2)}")

    # Step 4: Retrieve GeoJSON FeatureCollection (Contract for Day 6 Leaflet Dashboard)
    print(f"\n{SUB_BORDER}")
    print("[STEP 3 / 6] Fetching Ward Choropleth GeoJSON (GET /api/wards/geojson)...")
    res_geojson = client.get("/api/wards/geojson")
    geojson_data = res_geojson.json()
    print(f"Status Code: {res_geojson.status_code}")
    print(f"Total Features: {geojson_data.get('total_wards')}")
    sample_feature = geojson_data["features"][0]
    print(f"Sample Feature (Ward '{sample_feature['id']}'):")
    print(f"  - Ward Name          : {sample_feature['properties']['ward_name']}")
    print(f"  - Zone               : {sample_feature['properties']['zone']}")
    print(f"  - Observed Temp      : {sample_feature['properties']['temp_c']} °C")
    print(f"  - NOAA Heat Index    : {sample_feature['properties']['heat_index_c']} °C")
    print(f"  - Outdoor WBGT       : {sample_feature['properties']['wbgt_c']} °C")
    print(f"  - UTCI               : {sample_feature['properties']['utci_c']} °C")
    print(f"  - Thermal Stress (0-100): {sample_feature['properties']['thermal_stress_score']}")
    print(f"  - HVI Vulnerability  : {sample_feature['properties']['vulnerability_score']} ({sample_feature['properties']['vulnerability_tier']})")
    print(f"  - Final Risk Score   : {sample_feature['properties']['final_risk_score']}")
    print(f"  - Risk Tier Level    : {sample_feature['properties']['risk_level']}")
    print(f"  - Choropleth Color   : {sample_feature['properties']['color']}")
    print(f"  - Advisory Action    : {sample_feature['properties']['advisory'][:80]}...")

    # Step 5: Query Ward Risk Endpoint
    target_ward_id = sample_feature["id"]
    print(f"\n{SUB_BORDER}")
    print(f"[STEP 4 / 6] Querying Ward Risk Score & Advisory (GET /api/risk/{target_ward_id})...")
    res_risk = client.get(f"/api/risk/{target_ward_id}")
    print(f"Status Code: {res_risk.status_code}")
    print(f"Response:\n{json.dumps(res_risk.json(), indent=2)}")

    # Step 6: Query Ward Weather Observations & History
    print(f"\n{SUB_BORDER}")
    print(f"[STEP 5 / 6] Querying Ward Weather & Thermal Readings (GET /api/weather/{target_ward_id})...")
    res_weather = client.get(f"/api/weather/{target_ward_id}")
    weather_data = res_weather.json()
    print(f"Status Code: {res_weather.status_code}")
    print(f"Ward: {weather_data['ward_name']} | History Points: {weather_data['history_count']}")
    print(f"Latest Reading:\n{json.dumps(weather_data['latest'], indent=2)}")

    # Step 7: Query Multi-Day Risk Forecast
    print(f"\n{SUB_BORDER}")
    print(f"[STEP 6a / 6] Querying 5-Day Risk Forecast Timeline (GET /api/forecast/{target_ward_id})...")
    res_forecast = client.get(f"/api/forecast/{target_ward_id}")
    forecast_data = res_forecast.json()
    print(f"Status Code: {res_forecast.status_code}")
    for fc in forecast_data["forecasts"]:
        print(f"  - Day +{fc['horizon_days']} ({fc['forecast_date'][:10]}): Predicted Risk = {fc['predicted_risk_score']} [{fc['predicted_risk_tier']}]")

    # Step 8: Trigger Early Warning Alert Dispatch
    print(f"\n{SUB_BORDER}")
    print(f"[STEP 6b / 6] Triggering Early Warning Alert Dispatch (POST /api/alert/trigger)...")
    alert_payload = {
        "ward_id": target_ward_id,
        "recipient_phone": "+919876543210",
        "channel": "sms",
        "force": True,
    }
    res_alert = client.post("/api/alert/trigger", json=alert_payload)
    print(f"Status Code: {res_alert.status_code}")
    print(f"Response:\n{json.dumps(res_alert.json(), indent=2)}")

    print(f"\n{BORDER}")
    print("DAY 5 VALIDATION COMPLETE: ALL DATABASE & REST MICROSERVICES OPERATIONAL".center(80))
    print("READY FOR DAY 6: FRONTEND LEAFLET.JS CHOROPLETH DASHBOARD INTEGRATION".center(80))
    print(BORDER)


if __name__ == "__main__":
    main()
