"""Unit and Integration Tests for Anonymous Alert Subscriptions (Day 18).

Tests phone number validation, rate limiting, duplicate protection,
double opt-in confirmation messaging, STOP webhook processing,
REST API endpoints, and alert engine subscriber dispatch with daily safety caps.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.config import settings
from backend.db.session import SessionLocal
from backend.db.models_orm import (
    WardBoundary,
    WardVulnerability,
    WeatherReading,
    AlertSubscriber,
    ConsentLog,
    AlertLog,
)
from backend.subscriptions.subscription_service import (
    normalize_and_validate_phone,
    subscribe,
    unsubscribe,
    handle_stop_reply,
    check_rate_limit,
)
from backend.subscriptions.subscription_schema import SubscriptionChannel
from backend.alerts.alert_engine import check_and_trigger_alerts, reset_session_alert_count
from backend.models import RiskLevel


@pytest.fixture
def db_session():
    """Provide a transactional database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client():
    """FastAPI TestClient instance."""
    return TestClient(app)


class MockSender:
    """Mock alert sender capturing sent messages without network calls."""

    def __init__(self):
        self.sent_messages = []

    def send(self, to: str, message: str):
        self.sent_messages.append({"to": to, "message": message})
        return {
            "success": True,
            "message_id": f"MOCK_{len(self.sent_messages)}",
            "detail": "Mock message dispatched successfully.",
            "channel": "sms",
        }


def test_normalize_and_validate_phone_valid():
    """Verify phone normalization handles 10-digit Indian numbers and E.164 formats."""
    # 10-digit Indian mobile
    assert normalize_and_validate_phone("9876543210") == "+919876543210"
    # Formatted with spaces and hyphens
    assert normalize_and_validate_phone("+91 98765-43210") == "+919876543210"
    # Starting with 91 but no plus
    assert normalize_and_validate_phone("919876543210") == "+919876543210"
    # Valid E.164
    assert normalize_and_validate_phone("+919876543210") == "+919876543210"


def test_normalize_and_validate_phone_invalid():
    """Verify malformed or invalid phone numbers are strictly rejected."""
    with pytest.raises(ValueError):
        normalize_and_validate_phone("12345")
    with pytest.raises(ValueError):
        normalize_and_validate_phone("abcdefghij")
    with pytest.raises(ValueError):
        normalize_and_validate_phone("")


def test_subscribe_valid_flow(db_session):
    """Verify successful subscription, confirmation dispatch, and consent logging."""
    test_phone = "+919123456780"
    # Clean any prior test artifacts
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()

    mock_sender = MockSender()
    res = subscribe(
        phone_number=test_phone,
        ward_id="AMD_01",
        channel=SubscriptionChannel.SMS,
        db=db_session,
        sender=mock_sender,
    )

    assert res.success is True
    assert res.phone_number == test_phone
    assert res.ward_id == "AMD_01"
    assert res.channel == "sms"

    # Verify confirmation message was dispatched
    assert len(mock_sender.sent_messages) == 1
    assert "subscribed to heat alerts" in mock_sender.sent_messages[0]["message"]
    assert "STOP" in mock_sender.sent_messages[0]["message"]

    # Verify DB records
    sub = (
        db_session.query(AlertSubscriber)
        .filter(AlertSubscriber.phone_number == test_phone, AlertSubscriber.ward_id == "AMD_01")
        .first()
    )
    assert sub is not None
    assert sub.is_active is True

    consent = (
        db_session.query(ConsentLog)
        .filter(ConsentLog.phone_number == test_phone, ConsentLog.action == "SUBSCRIBE_OPT_IN")
        .first()
    )
    assert consent is not None
    assert "STOP" in consent.message_text

    # Cleanup
    db_session.delete(sub)
    db_session.delete(consent)
    db_session.commit()


def test_subscribe_duplicate_rejected(db_session):
    """Verify subscribing an already actively subscribed phone to the same ward raises ValueError."""
    test_phone = "+919123456781"
    mock_sender = MockSender()

    # Clean prior
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.commit()

    # First subscription succeeds
    subscribe(
        phone_number=test_phone,
        ward_id="AMD_01",
        channel=SubscriptionChannel.SMS,
        db=db_session,
        sender=mock_sender,
    )

    # Second subscription to identical ward must fail
    with pytest.raises(ValueError, match="already actively subscribed"):
        subscribe(
            phone_number=test_phone,
            ward_id="AMD_01",
            channel=SubscriptionChannel.SMS,
            db=db_session,
            sender=mock_sender,
        )

    # Cleanup
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()


def test_subscribe_rate_limiting(db_session):
    """Verify max subscription attempts per hour enforcement."""
    test_phone = "+919123456782"
    now_utc = datetime.now(timezone.utc)

    # Clean prior
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()

    # Seed 3 attempts in the past hour
    for i in range(3):
        db_session.add(
            ConsentLog(
                phone_number=test_phone,
                ward_id="AMD_01",
                action="SUBSCRIBE_ATTEMPT",
                channel="sms",
                message_text=f"Attempt {i}",
                delivery_status="attempted",
                recorded_at=now_utc - timedelta(minutes=5 * i),
            )
        )
    db_session.commit()

    # Attempting a 4th should be blocked by rate limiting
    with pytest.raises(ValueError, match="Rate limit exceeded"):
        check_rate_limit(test_phone, db_session)

    # Cleanup
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()


def test_unsubscribe_flow(db_session):
    """Verify unsubscribing deactivates subscriber and logs opt-out."""
    test_phone = "+919123456783"
    mock_sender = MockSender()

    # Clean prior
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.commit()

    # Subscribe
    subscribe(
        phone_number=test_phone,
        ward_id="AMD_01",
        channel=SubscriptionChannel.SMS,
        db=db_session,
        sender=mock_sender,
    )

    # Unsubscribe
    unsub_res = unsubscribe(
        phone_number=test_phone,
        ward_id="ALL",
        db=db_session,
        sender=mock_sender,
    )

    assert unsub_res.success is True
    assert unsub_res.deactivated_count >= 1

    # Verify subscriber record is deactivated
    sub = (
        db_session.query(AlertSubscriber)
        .filter(AlertSubscriber.phone_number == test_phone, AlertSubscriber.ward_id == "AMD_01")
        .first()
    )
    assert sub.is_active is False

    # Verify opt-out confirmation message was dispatched
    last_msg = mock_sender.sent_messages[-1]["message"]
    assert "unsubscribed" in last_msg
    assert "START" in last_msg

    # Cleanup
    db_session.delete(sub)
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()


def test_handle_stop_reply_webhook(db_session):
    """Verify carrier inbound webhook for STOP/UNSUBSCRIBE deactivates active subscriptions."""
    test_phone = "+919123456784"
    mock_sender = MockSender()

    # Clean prior
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.commit()

    # Subscribe
    subscribe(
        phone_number=test_phone,
        ward_id="AMD_01",
        channel=SubscriptionChannel.SMS,
        db=db_session,
        sender=mock_sender,
    )

    # Handle STOP keyword (case-insensitive)
    webhook_res = handle_stop_reply(
        phone_number=test_phone,
        message_text="stop",
        db=db_session,
        sender=mock_sender,
    )

    assert webhook_res.handled is True
    assert webhook_res.action == "UNSUBSCRIBED"

    # Verify subscriber deactivated
    sub = (
        db_session.query(AlertSubscriber)
        .filter(AlertSubscriber.phone_number == test_phone, AlertSubscriber.ward_id == "AMD_01")
        .first()
    )
    assert sub.is_active is False

    # Cleanup
    db_session.delete(sub)
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()


def test_api_subscribe_and_webhook_endpoints(test_client, db_session):
    """Test REST API /api/subscribe, /api/unsubscribe, and /api/webhook/inbound-message."""
    test_phone = "+919123456785"

    # Clean prior
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()

    # 1. Test POST /api/subscribe
    payload = {
        "phone_number": "9123456785",
        "ward_id": "AMD_01",
        "channel": "sms",
    }
    res = test_client.post("/api/subscribe", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["phone_number"] == test_phone
    assert data["ward_id"] == "AMD_01"

    # 2. Test Inbound Webhook POST /api/webhook/inbound-message (Twilio form-data / JSON)
    webhook_res = test_client.post(
        "/api/webhook/inbound-message",
        content=f"From={test_phone}&Body=STOP",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert webhook_res.status_code == 200
    w_data = webhook_res.json()
    assert w_data["handled"] is True
    assert w_data["action"] == "UNSUBSCRIBED"

    # Verify DB deactivation
    sub = (
        db_session.query(AlertSubscriber)
        .filter(AlertSubscriber.phone_number == test_phone)
        .first()
    )
    assert sub.is_active is False

    # 3. Test POST /api/unsubscribe
    unsub_res = test_client.post(
        "/api/unsubscribe",
        json={"phone_number": test_phone, "ward_id": "ALL"},
    )
    assert unsub_res.status_code == 200

    # Cleanup
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.query(ConsentLog).filter(ConsentLog.phone_number == test_phone).delete()
    db_session.commit()


def test_alert_engine_dispatches_to_active_subscribers(db_session):
    """Verify check_and_trigger_alerts sends to registered subscribers in breached wards."""
    test_phone = "+919123456786"
    now_utc = datetime.now(timezone.utc)
    reset_session_alert_count()

    # Clean prior
    db_session.query(AlertSubscriber).filter(AlertSubscriber.phone_number == test_phone).delete()
    db_session.query(AlertLog).filter(AlertLog.recipient_phone == test_phone).delete()
    db_session.commit()

    # Register active subscriber in AMD_17 (Vatva - high vulnerability ward)
    sub = AlertSubscriber(
        phone_number=test_phone,
        ward_id="AMD_17",
        channel="sms",
        subscribed_at=now_utc,
        is_active=True,
        consent_confirmed_at=now_utc,
        last_alert_sent_at=None,
    )
    db_session.add(sub)

    # Seed extreme thermal reading for AMD_17 to guarantee risk >= 0.70
    reading = WeatherReading(
        ward_id="AMD_17",
        timestamp=now_utc,
        temp_c=46.5,
        humidity_pct=45.0,
        wind_speed_ms=2.0,
        solar_radiation_wm2=900.0,
        source="era5",
        heat_index_c=52.0,
        wbgt_c=38.0,
        utci_c=46.0,
        thermal_stress_score=95.0,
    )
    db_session.add(reading)
    db_session.commit()

    mock_sender = MockSender()
    results = check_and_trigger_alerts(
        db=db_session,
        sender=mock_sender,
        target_phone="+919999999999",  # Different demo phone
    )

    # Find alert sent to test_phone
    subscriber_alerts = [r for r in results if r.recipient_phone == test_phone]
    assert len(subscriber_alerts) >= 1
    assert subscriber_alerts[0].success is True

    # Refresh subscriber and verify last_alert_sent_at was stamped
    db_session.refresh(sub)
    assert sub.last_alert_sent_at is not None

    # Cleanup
    db_session.delete(sub)
    db_session.delete(reading)
    db_session.query(AlertLog).filter(AlertLog.recipient_phone == test_phone).delete()
    db_session.commit()
