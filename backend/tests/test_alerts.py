"""Unit tests for Early Warning Alert System (Twilio/Gupshup Gateway & Alert Engine).

Uses isolated in-memory SQLite fixtures and mocked AlertSender interfaces.
Guaranteed zero external network requests or live billable SMS dispatches.
"""

from datetime import datetime, timezone
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.models import AlertChannel, RiskLevel
from backend.db.session import init_db
from backend.db.models_orm import WardBoundary, WardVulnerability, WeatherReading, AlertLog
from backend.alerts.sender_base import AlertSender
from backend.alerts.twilio_client import TwilioAlertSender
from backend.alerts.gupshup_client import GupshupAlertSender
from backend.alerts.alert_engine import (
    compose_public_health_advisory,
    send_ward_alert,
    check_and_trigger_alerts,
    reset_session_alert_count,
)


class MockAlertSender(AlertSender):
    """Deterministic in-memory mock for notification gateway."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_messages = []

    def send(self, to: str, message: str):
        self.sent_messages.append({"to": to, "message": message})
        return {
            "success": self.should_succeed,
            "message_id": f"MOCK-MSG-{len(self.sent_messages)}",
            "detail": "Mock delivery confirmed.",
            "channel": "sms",
        }


@pytest.fixture
def in_memory_alert_db():
    """In-memory SQLite database populated with high and low risk wards."""
    reset_session_alert_count()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    # 1. High-risk Ward
    ward_high = WardBoundary(
        ward_id="AMD_DANGER",
        ward_name="Jamalpur High Risk",
        geometry_geojson=json.dumps({"type": "Point", "coordinates": [72.58, 23.01]}),
        city="Ahmedabad",
    )
    session.add(ward_high)
    vuln_high = WardVulnerability(
        ward_id="AMD_DANGER",
        elderly_pct=18.0,
        outdoor_worker_pct=38.0,
        slum_pct=42.0,
        green_cover_pct=5.0,
        hospital_bed_density=1.0,
        vulnerability_score=0.82,
        risk_tier="Extreme",
    )
    session.add(vuln_high)
    weather_high = WeatherReading(
        ward_id="AMD_DANGER",
        timestamp=datetime.now(timezone.utc),
        temp_c=43.5,
        humidity_pct=48.0,
        wind_speed_ms=2.5,
        solar_radiation_wm2=900.0,
        source="open_meteo",
        heat_index_c=52.0,
        wbgt_c=34.5,
        utci_c=46.0,
        thermal_stress_score=92.0,
    )
    session.add(weather_high)

    # 2. Low-risk Ward
    ward_low = WardBoundary(
        ward_id="AMD_SAFE",
        ward_name="Bodakdev Safe",
        geometry_geojson=json.dumps({"type": "Point", "coordinates": [72.51, 23.04]}),
        city="Ahmedabad",
    )
    session.add(ward_low)
    vuln_low = WardVulnerability(
        ward_id="AMD_SAFE",
        elderly_pct=10.0,
        outdoor_worker_pct=8.0,
        slum_pct=2.0,
        green_cover_pct=28.0,
        hospital_bed_density=4.5,
        vulnerability_score=0.15,
        risk_tier="Low",
    )
    session.add(vuln_low)
    weather_low = WeatherReading(
        ward_id="AMD_SAFE",
        timestamp=datetime.now(timezone.utc),
        temp_c=28.0,
        humidity_pct=40.0,
        wind_speed_ms=4.0,
        solar_radiation_wm2=400.0,
        source="open_meteo",
        heat_index_c=28.0,
        wbgt_c=24.0,
        utci_c=27.0,
        thermal_stress_score=20.0,
    )
    session.add(weather_low)

    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_compose_public_health_advisory_contents():
    """Ensure WHO/GHHIN advisories contain mandatory public health warnings."""
    extreme_adv = compose_public_health_advisory("Jamalpur", "AMD_01", RiskLevel.EXTREME, temp_c=44.0, wbgt_c=34.0)
    assert "CRITICAL HEAT EMERGENCY" in extreme_adv
    assert "heatstroke" in extreme_adv.lower()
    assert "cooling shelters" in extreme_adv.lower()
    assert "108" in extreme_adv

    moderate_adv = compose_public_health_advisory("Navrangpura", "AMD_02", RiskLevel.MODERATE)
    assert "HEAT CAUTION" in moderate_adv


def test_send_ward_alert_high_risk_success(in_memory_alert_db):
    """Ensure alert triggers, calls sender, and persists to AlertLog."""
    mock_sender = MockAlertSender()
    response = send_ward_alert(
        ward_id="AMD_DANGER",
        recipient_phone="+919876543210",
        channel=AlertChannel.SMS,
        force=False,
        db=in_memory_alert_db,
        sender=mock_sender,
    )

    assert response.success is True
    assert len(mock_sender.sent_messages) == 1
    assert mock_sender.sent_messages[0]["to"] == "+919876543210"

    # Verify AlertLog persistence
    logs = in_memory_alert_db.query(AlertLog).filter_by(ward_id="AMD_DANGER").all()
    assert len(logs) == 1
    assert logs[0].risk_tier in ["VERY_HIGH", "EXTREME"]
    assert logs[0].success is True


def test_send_ward_alert_low_risk_withheld(in_memory_alert_db):
    """Ensure low-risk wards do not trigger alerts unless force=True."""
    mock_sender = MockAlertSender()
    response = send_ward_alert(
        ward_id="AMD_SAFE",
        recipient_phone="+919876543210",
        channel=AlertChannel.SMS,
        force=False,
        db=in_memory_alert_db,
        sender=mock_sender,
    )

    assert response.success is False
    assert "withheld" in response.detail.lower()
    assert len(mock_sender.sent_messages) == 0


def test_send_ward_alert_forced_override(in_memory_alert_db):
    """Ensure force=True allows manual demo testing on any ward."""
    mock_sender = MockAlertSender()
    response = send_ward_alert(
        ward_id="AMD_SAFE",
        recipient_phone="+919876543210",
        channel=AlertChannel.WHATSAPP,
        force=True,
        db=in_memory_alert_db,
        sender=mock_sender,
    )

    assert response.success is True
    assert len(mock_sender.sent_messages) == 1


def test_demo_rate_limit_protection(in_memory_alert_db):
    """Ensure demo rate limit stops repeated dispatches."""
    reset_session_alert_count()
    mock_sender = MockAlertSender()

    # Fire up to limit (5)
    for _ in range(settings.max_alerts_per_demo_run):
        res = send_ward_alert(
            ward_id="AMD_DANGER",
            recipient_phone="+919876543210",
            force=False,
            db=in_memory_alert_db,
            sender=mock_sender,
        )
        assert res.success is True

    # 6th attempt should be blocked by safety limit
    blocked_res = send_ward_alert(
        ward_id="AMD_DANGER",
        recipient_phone="+919876543210",
        force=False,
        db=in_memory_alert_db,
        sender=mock_sender,
    )
    assert blocked_res.success is False
    assert "safety limit reached" in blocked_res.detail.lower()


def test_check_and_trigger_alerts_scan(in_memory_alert_db):
    """Ensure check_and_trigger_alerts scans wards and dispatches for danger wards only."""
    reset_session_alert_count()
    mock_sender = MockAlertSender()
    results = check_and_trigger_alerts(db=in_memory_alert_db, sender=mock_sender)

    assert len(results) == 1
    assert results[0].ward_id == "AMD_DANGER"


def test_twilio_and_gupshup_sandbox_modes():
    """Verify Twilio and Gupshup sandbox simulators work cleanly without credentials."""
    twilio = TwilioAlertSender()
    tw_res = twilio.send("+919876543210", "Test Twilio Alert")
    assert tw_res["success"] is True
    assert tw_res["message_id"].startswith("SM")

    gupshup = GupshupAlertSender()
    gs_res = gupshup.send("+919876543210", "Test Gupshup Alert")
    assert gs_res["success"] is True
    assert gs_res["message_id"].startswith("GS")
