"""Automated Heatwave Early Warning Alert Engine.

Monitors ward risk levels, generates standardized WHO/GHHIN/NDMA public health advisories,
enforces demo rate-limiting safety guards, dispatches alerts via configured gateways,
and maintains persistent audit records in the database.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import settings
from backend.models import AlertChannel, AlertResponse, RiskLevel
from backend.db.models_orm import WardBoundary, WeatherReading, AlertLog
from backend.alerts.sender_base import AlertSender
from backend.alerts.twilio_client import TwilioAlertSender
from backend.alerts.gupshup_client import GupshupAlertSender
from backend.vulnerability_model.health_consequence_map import get_population_impact

logger = logging.getLogger(__name__)

# In-memory session counter for demo safety guard
_SESSION_ALERT_DISPATCH_COUNT = 0


def get_session_alert_count() -> int:
    """Return count of alerts dispatched during current server lifecycle."""
    return _SESSION_ALERT_DISPATCH_COUNT


def reset_session_alert_count() -> None:
    """Reset the demo alert counter (used in tests and fresh demos)."""
    global _SESSION_ALERT_DISPATCH_COUNT
    _SESSION_ALERT_DISPATCH_COUNT = 0


def compose_public_health_advisory(
    ward_name: str,
    ward_id: str,
    risk_level: RiskLevel,
    temp_c: Optional[float] = None,
    wbgt_c: Optional[float] = None,
    dominant_action_info: Optional[str] = None,
) -> str:
    """Compose public health heat advisory conforming to WHO/GHHIN standards, enriched with cohort action (Part E)."""
    temp_info = f" (Observed: {temp_c:.1f}°C, WBGT: {wbgt_c:.1f}°C)" if temp_c and wbgt_c else ""
    action_suffix = f" Priority Action: {dominant_action_info}" if dominant_action_info else ""

    if risk_level == RiskLevel.EXTREME:
        msg = (
            f"🚨 CRITICAL HEAT EMERGENCY for {ward_name} [{ward_id}]{temp_info}: "
            "Severe risk of life-threatening heatstroke! Cease all outdoor physical labor immediately. "
            "Stay indoors in shaded/cooled rooms. Drink water with ORS/electrolytes every 20 minutes. "
            "Vulnerable elderly and children must report to municipal cooling shelters. Emergency helpline: 108."
        )
    elif risk_level == RiskLevel.VERY_HIGH:
        msg = (
            f"⚠️ SEVERE HEAT ADVISORY for {ward_name} [{ward_id}]{temp_info}: "
            "High danger of heat exhaustion. Avoid direct sun and heavy outdoor labor between 11:00 AM - 4:30 PM. "
            "Stay hydrated and utilize municipal shaded rest points. Watch for dizziness or rapid pulse."
        )
    elif risk_level == RiskLevel.HIGH:
        msg = (
            f"⚠️ HEAT ALERT for {ward_name} [{ward_id}]{temp_info}: "
            "High thermal stress. Hydrate frequently, wear light breathable clothing, and check on elderly neighbors."
        )
    elif risk_level == RiskLevel.MODERATE:
        msg = (
            f"HEAT CAUTION for {ward_name} [{ward_id}]: "
            "Moderate heat conditions. Outdoor workers should take periodic shaded breaks and maintain hydration."
        )
    else:
        msg = f"NORMAL CONDITIONS for {ward_name} [{ward_id}]: Baseline municipal heat preparedness active."

    return f"{msg}{action_suffix}"


def send_ward_alert(
    ward_id: str,
    recipient_phone: str,
    channel: AlertChannel = AlertChannel.SMS,
    force: bool = False,
    db: Optional[Session] = None,
    sender: Optional[AlertSender] = None,
) -> AlertResponse:
    """Evaluate and dispatch an early warning alert for a specific ward.

    Parameters
    ----------
    ward_id : str
        Target municipal ward.
    recipient_phone : str
        Recipient phone number.
    channel : AlertChannel, optional
        Communication channel (SMS, WhatsApp, Webhook).
    force : bool, optional
        Bypass threshold checks and safety limits for manual testing.
    db : Optional[Session], optional
        Active database session for retrieving ward data and logging audit trails.
    sender : Optional[AlertSender], optional
        Custom or mocked sender instance (ideal for automated testing).

    Returns
    -------
    AlertResponse
        Confirmation payload with delivery status.
    """
    global _SESSION_ALERT_DISPATCH_COUNT

    # 1. Check Safety Rate Limit for Demo Runs
    if not force and _SESSION_ALERT_DISPATCH_COUNT >= settings.max_alerts_per_demo_run:
        msg = (
            f"Safety limit reached: Maximum {settings.max_alerts_per_demo_run} alerts permitted "
            "per demo session to prevent accidental SMS spamming. Use force=True to bypass."
        )
        logger.warning(msg)
        return AlertResponse(
            success=False,
            message_id=None,
            ward_id=ward_id,
            recipient_phone=recipient_phone,
            channel=channel,
            dispatched_at=datetime.now(timezone.utc),
            detail=msg,
        )

    # 2. Retrieve Ward & Latest Risk Level
    ward_name = ward_id
    risk_level = RiskLevel.HIGH
    temp_c = None
    wbgt_c = None
    dominant_action_info = None

    if db is not None:
        ward = db.query(WardBoundary).filter(WardBoundary.ward_id == ward_id).first()
        if not ward:
            raise ValueError(f"Ward '{ward_id}' not found in database.")
        ward_name = ward.ward_name

        latest_weather = (
            db.query(WeatherReading)
            .filter(WeatherReading.ward_id == ward_id)
            .order_by(desc(WeatherReading.timestamp))
            .first()
        )

        vuln_score = ward.vulnerability.vulnerability_score if ward.vulnerability else 0.50
        hazard_score = (latest_weather.thermal_stress_score / 100.0) if latest_weather else 0.70
        if latest_weather:
            temp_c = latest_weather.temp_c
            wbgt_c = latest_weather.wbgt_c

        final_risk = round(0.60 * hazard_score + 0.40 * vuln_score, 4)
        if final_risk < 0.25:
            risk_level = RiskLevel.LOW
        elif final_risk < 0.50:
            risk_level = RiskLevel.MODERATE
        elif final_risk < 0.70:
            risk_level = RiskLevel.HIGH
        elif final_risk < 0.85:
            risk_level = RiskLevel.VERY_HIGH
        else:
            risk_level = RiskLevel.EXTREME

        # Part E: Extract dominant demographic cohort action for targeted alerting
        if ward.vulnerability:
            try:
                impact = get_population_impact(
                    ward_data=ward.vulnerability,
                    risk_tier=risk_level,
                    final_risk_score=final_risk,
                )
                dom_driver = impact.get("dominant_risk_factor", "")
                segments = impact.get("segments", {})
                if "Outdoor" in dom_driver and "outdoor_workers" in segments:
                    dominant_action_info = segments["outdoor_workers"]["action"]
                elif "Slum" in dom_driver and "slum_residents" in segments:
                    dominant_action_info = segments["slum_residents"]["action"]
                elif "Elderly" in dom_driver and "elderly_60plus" in segments:
                    dominant_action_info = segments["elderly_60plus"]["action"]
                elif segments:
                    highest_seg = max(segments.values(), key=lambda s: s.get("estimated_count", 0))
                    dominant_action_info = highest_seg.get("action")
            except Exception as err:
                logger.warning("Could not derive cohort dominant action for ward %s: %s", ward_id, err)

    # 3. Severity Threshold Evaluation
    if not force and risk_level in [RiskLevel.LOW, RiskLevel.MODERATE]:
        return AlertResponse(
            success=False,
            message_id=None,
            ward_id=ward_id,
            recipient_phone=recipient_phone,
            channel=channel,
            dispatched_at=datetime.now(timezone.utc),
            detail=(
                f"Alert withheld: Current risk tier for {ward_name} is '{risk_level.value}'. "
                f"Configured alert threshold is '{settings.alert_risk_threshold}'. Use force=True to bypass."
            ),
        )

    # 4. Compose WHO/GHHIN Advisory Text (Enriched with targeted cohort action)
    advisory_message = compose_public_health_advisory(
        ward_name=ward_name,
        ward_id=ward_id,
        risk_level=risk_level,
        temp_c=temp_c,
        wbgt_c=wbgt_c,
        dominant_action_info=dominant_action_info,
    )

    # 5. Resolve Notification Sender Gateway
    if sender is None:
        if channel == AlertChannel.WHATSAPP:
            sender = TwilioAlertSender(is_whatsapp=True)
        else:
            sender = TwilioAlertSender(is_whatsapp=False)

    # 6. Execute Dispatch
    dispatch_result = sender.send(to=recipient_phone, message=advisory_message)
    _SESSION_ALERT_DISPATCH_COUNT += 1

    # 7. Record Audit Trail in Persistent Database
    now_utc = datetime.now(timezone.utc)
    if db is not None:
        log_entry = AlertLog(
            ward_id=ward_id,
            triggered_at=now_utc,
            risk_tier=risk_level.value,
            message_sent=advisory_message,
            channel=channel.value,
            recipient_phone=recipient_phone,
            recipient_count=1,
            success=dispatch_result.get("success", True),
        )
        db.add(log_entry)
        db.commit()

    return AlertResponse(
        success=dispatch_result.get("success", True),
        message_id=dispatch_result.get("message_id", f"MSG-{uuid.uuid4().hex[:8].upper()}"),
        ward_id=ward_id,
        recipient_phone=recipient_phone,
        channel=channel,
        dispatched_at=now_utc,
        detail=dispatch_result.get("detail", f"Dispatched alert for {ward_name} ({risk_level.value})."),
    )


def check_and_trigger_alerts(
    db: Session,
    sender: Optional[AlertSender] = None,
    target_phone: Optional[str] = None,
) -> List[AlertResponse]:
    """Scan all wards and dispatch automated alerts for those exceeding danger thresholds."""
    wards = db.query(WardBoundary).all()
    results = []
    phone = target_phone or settings.test_recipient_phone

    logger.info("Scanning %d wards for automated heatwave alert triggers...", len(wards))
    for ward in wards:
        latest_weather = (
            db.query(WeatherReading)
            .filter(WeatherReading.ward_id == ward.ward_id)
            .order_by(desc(WeatherReading.timestamp))
            .first()
        )
        vuln_score = ward.vulnerability.vulnerability_score if ward.vulnerability else 0.50
        hazard_score = (latest_weather.thermal_stress_score / 100.0) if latest_weather else 0.60
        final_risk = round(0.60 * hazard_score + 0.40 * vuln_score, 4)

        # Trigger if high or extreme risk
        if final_risk >= 0.70:
            logger.info("Ward %s breached alert threshold (Risk: %.3f). Triggering alert dispatch...", ward.ward_id, final_risk)
            try:
                res = send_ward_alert(
                    ward_id=ward.ward_id,
                    recipient_phone=phone,
                    channel=AlertChannel.SMS,
                    force=False,
                    db=db,
                    sender=sender,
                )
                results.append(res)
            except Exception as e:
                logger.error("Failed to trigger alert for ward %s: %s", ward.ward_id, e)

    return results
