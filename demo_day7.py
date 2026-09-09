"""SIH26083 - Day 7 Demonstration Script: Multi-Day Forecasting & Automated Early Warning Alerts.

Demonstrates:
1. Running the multi-day predictive risk forecasting batch job across all municipal wards.
2. Querying the forecast timeline from the persistent database.
3. Simulating an extreme heatwave threshold breach on a high-density informal ward.
4. Generating a WHO/GHHIN-compliant public health emergency heat advisory.
5. Dispatching the alert via Twilio / Gupshup Sandbox gateway.
6. Verifying that the alert dispatch is permanently audited in the database AlertLog.
"""

import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.session import SessionLocal, init_db
from backend.db.models_orm import WardBoundary, WeatherReading, RiskForecast, AlertLog
from backend.forecasting.run_forecast_job import run_forecast_job
from backend.alerts.alert_engine import send_ward_alert, reset_session_alert_count
from backend.models import AlertChannel

BORDER = "=" * 80
SUB_BORDER = "-" * 80


def print_banner(text: str):
    print(f"\n{BORDER}\n{text.center(80)}\n{BORDER}")


def main():
    print_banner("SIH26083: DAY 7 DEMO - FORECASTING & AUTOMATED ALERTING")

    init_db()
    db: Session = SessionLocal()
    reset_session_alert_count()

    try:
        # ----------------------------------------------------------------------
        # PART 1: Multi-Day Predictive Risk Forecasting Job
        # ----------------------------------------------------------------------
        print("\n[STEP 1 / 4] Running Predictive Heatwave Forecast Batch Job (Horizons 1 to 5 Days)...")
        job_result = run_forecast_job(db=db, horizon_days=5, clear_existing=True)
        print(f" -> Processed {job_result['wards_processed']} wards.")
        print(f" -> Generated and persisted {job_result['forecasts_generated']} daily forecast records into 'risk_forecasts' table.")

        # Inspect sample forecast timeline
        sample_ward = db.query(WardBoundary).first()
        sample_id = sample_ward.ward_id if sample_ward else "AMD_01"
        sample_name = sample_ward.ward_name if sample_ward else "Navrangpura"

        forecasts = (
            db.query(RiskForecast)
            .filter(RiskForecast.ward_id == sample_id)
            .order_by(RiskForecast.forecast_horizon_days.asc())
            .all()
        )

        print(f"\n{SUB_BORDER}")
        print(f"[STEP 2 / 4] 5-Day Predictive Risk Projections for '{sample_name}' ({sample_id}):")
        for fc in forecasts:
            date_str = fc.forecast_date.strftime("%Y-%m-%d")
            print(f"  • Day +{fc.forecast_horizon_days} [{date_str}]: "
                  f"Predicted Risk = {fc.predicted_risk_score:.4f} "
                  f"| Tier = {fc.predicted_risk_tier.ljust(10)}")

        # ----------------------------------------------------------------------
        # PART 2: Simulated Extreme Heatwave Breach & Automated Early Warning
        # ----------------------------------------------------------------------
        print(f"\n{SUB_BORDER}")
        print("[STEP 3 / 4] Simulating Extreme Heatwave Threshold Breach on Target Ward...")
        
        # Select target ward for demonstration
        target_ward = db.query(WardBoundary).filter(WardBoundary.ward_id.in_(["AMD_18", "AMD_01", sample_id])).first()
        target_id = target_ward.ward_id
        target_name = target_ward.ward_name

        recipient_phone = settings.test_recipient_phone
        print(f" -> Target Ward        : {target_name} ({target_id})")
        print(f" -> Recipient Channel  : SMS / WhatsApp (Twilio/Gupshup Gateway)")
        print(f" -> Destination Phone  : {recipient_phone}")
        print(f" -> Trigger Mode       : Automated Civic Early Warning (Bypass threshold override enabled for demo)")

        # Dispatch alert using the Alert Engine
        alert_response = send_ward_alert(
            ward_id=target_id,
            recipient_phone=recipient_phone,
            channel=AlertChannel.SMS,
            force=True,
            db=db,
        )

        print(f"\n{SUB_BORDER}")
        print("[STEP 4 / 4] Early Warning Dispatch Results & Delivery Audit:")
        print(f"  • Delivery Success   : {alert_response.success}")
        print(f"  • Message ID / SID   : {alert_response.message_id}")
        print(f"  • Gateway Channel    : {alert_response.channel.value.upper()}")
        print(f"  • Dispatched At      : {alert_response.dispatched_at.isoformat()}")
        print(f"  • Gateway Response   : {alert_response.detail}")

        # Check Audit Log in Database
        latest_audit = (
            db.query(AlertLog)
            .filter(AlertLog.ward_id == target_id)
            .order_by(AlertLog.triggered_at.desc())
            .first()
        )

        if latest_audit:
            print("\n  [DATABASE AUDIT TRAIL VERIFIED]")
            print(f"  - Audit Log ID       : #{latest_audit.id}")
            print(f"  - Severity Level     : {latest_audit.risk_tier}")
            print(f"  - Recipient Number   : {latest_audit.recipient_phone}")
            print(f"  - Advisory Content   :\n    \"{latest_audit.message_sent}\"")

        print_banner("DAY 7 DEMONSTRATION COMPLETE: FORECASTING & ALERTS OPERATIONAL")

    finally:
        db.close()


if __name__ == "__main__":
    main()
