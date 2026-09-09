"""Alerts package for SIH26083 Extreme Heatwave Early Warning System."""

from backend.alerts.sender_base import AlertSender
from backend.alerts.twilio_client import TwilioAlertSender
from backend.alerts.gupshup_client import GupshupAlertSender
from backend.alerts.alert_engine import (
    compose_public_health_advisory,
    send_ward_alert,
    check_and_trigger_alerts,
    get_session_alert_count,
    reset_session_alert_count,
)

__all__ = [
    "AlertSender",
    "TwilioAlertSender",
    "GupshupAlertSender",
    "compose_public_health_advisory",
    "send_ward_alert",
    "check_and_trigger_alerts",
    "get_session_alert_count",
    "reset_session_alert_count",
]
