"""Subscription Service for Anonymous Phone/WhatsApp Heatwave Alerts.

Manages double opt-in subscriptions, phone validation, hourly abuse prevention,
automated confirmation messaging via Twilio/Gupshup, audit logging,
and compliance-mandated STOP keyword webhook handling.
"""

import re
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False
    NumberParseException = Exception

from backend.config import settings
from backend.db.session import SessionLocal
from backend.db.models_orm import AlertSubscriber, ConsentLog, WardBoundary
from backend.personal_risk.personal_risk_engine import resolve_user_location
from backend.alerts.sender_base import AlertSender
from backend.alerts.twilio_client import TwilioAlertSender
from backend.alerts.gupshup_client import GupshupAlertSender
from backend.subscriptions.subscription_schema import (
    SubscriptionChannel,
    SubscribeResponse,
    UnsubscribeResponse,
    InboundWebhookResponse,
)

logger = logging.getLogger(__name__)

# Standard STOP keywords recognized across international carrier compliance standards
STOP_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit", "arret"}
RESUME_KEYWORDS = {"start", "unstop", "subscribe"}


def normalize_and_validate_phone(raw_phone: str) -> str:
    """Validate and normalize a phone number into strict E.164 international format.

    Supports 10-digit Indian mobile numbers (automatically prefixing +91) as well
    as international E.164 phone numbers.

    Parameters
    ----------
    raw_phone : str
        Input string representing the phone number.

    Returns
    -------
    str
        Normalized E.164 phone string (e.g. '+919876543210').

    Raises
    ------
    ValueError
        If the phone number is invalid, malformed, or fails checksums.
    """
    if not raw_phone or not isinstance(raw_phone, str):
        raise ValueError("Phone number must be a non-empty string.")

    cleaned = raw_phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned.replace("whatsapp:", "")

    # Prepend '+' if missing and starts with 91 or 10-digit Indian mobile
    if not cleaned.startswith("+"):
        if len(cleaned) == 10 and cleaned[0] in "56789":
            cleaned = "+91" + cleaned
        elif len(cleaned) == 12 and cleaned.startswith("91"):
            cleaned = "+" + cleaned

    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(cleaned, "IN")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError(f"Phone number '{raw_phone}' is not a valid recognized telephone number.")
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException as e:
            # Fallback to strict E.164 regex if phonenumbers parser fails
            e164_pattern = re.compile(r"^\+[1-9]\d{9,14}$")
            if e164_pattern.match(cleaned):
                return cleaned
            raise ValueError(f"Invalid phone number format '{raw_phone}': {e}")
    else:
        # Resilient fallback if phonenumbers library is not installed
        e164_pattern = re.compile(r"^\+[1-9]\d{9,14}$")
        if e164_pattern.match(cleaned):
            return cleaned
        digits = re.sub(r"[^\d]", "", cleaned)
        if len(digits) == 10 and digits[0] in "56789":
            return f"+91{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        elif len(digits) >= 10:
            return f"+{digits}"
        raise ValueError(f"Invalid phone number format '{raw_phone}'. Must have at least 10 valid digits.")


def check_rate_limit(phone_number: str, db: Session) -> None:
    """Enforce abuse protection: max attempts per phone number per hour.

    Parameters
    ----------
    phone_number : str
        Normalized E.164 phone number.
    db : Session
        Active database session.

    Raises
    ------
    ValueError
        If attempts within the last 1 hour exceed configured threshold.
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    attempt_count = (
        db.query(ConsentLog)
        .filter(
            ConsentLog.phone_number == phone_number,
            ConsentLog.recorded_at >= one_hour_ago,
            ConsentLog.action.in_(["SUBSCRIBE_ATTEMPT", "SUBSCRIBE_OPT_IN"]),
        )
        .count()
    )

    limit = settings.max_subscription_attempts_per_hour
    if attempt_count >= limit:
        msg = (
            f"Rate limit exceeded: Maximum {limit} subscription attempts allowed "
            "per phone number per hour. Please wait before trying again."
        )
        logger.warning("Subscription rate limit reached for %s (count=%d).", phone_number, attempt_count)
        raise ValueError(msg)


def subscribe(
    phone_number: str,
    ward_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    channel: SubscriptionChannel = SubscriptionChannel.SMS,
    db: Optional[Session] = None,
    sender: Optional[AlertSender] = None,
) -> SubscribeResponse:
    """Subscribe a citizen phone number to hyper-local heatwave alerts with double opt-in.

    Validates phone format, enforces rate limits, checks for existing active subscriptions,
    persists or reactivates subscriber record, and dispatches an immediate confirmation
    message detailing opt-out instructions.
    """
    if db is None:
        with SessionLocal() as session:
            return subscribe(
                phone_number=phone_number,
                ward_id=ward_id,
                lat=lat,
                lon=lon,
                channel=channel,
                db=session,
                sender=sender,
            )

    # 1. Phone number normalization & validation
    normalized_phone = normalize_and_validate_phone(phone_number)

    # 2. Rate limiting check
    check_rate_limit(normalized_phone, db)

    # 3. Resolve location to ward
    resolved_ward_id, resolved_ward_name, _, _ = resolve_user_location(
        ward_id=ward_id,
        lat=lat,
        lon=lon,
        db=db,
    )

    # 4. Check for existing active subscription
    existing_active = (
        db.query(AlertSubscriber)
        .filter(
            AlertSubscriber.phone_number == normalized_phone,
            AlertSubscriber.ward_id == resolved_ward_id,
            AlertSubscriber.is_active == True,
        )
        .first()
    )
    if existing_active:
        raise ValueError(
            f"Phone number {normalized_phone} is already actively subscribed to alerts for {resolved_ward_name} [{resolved_ward_id}]."
        )

    # 5. Create or reactivate subscriber record
    now_utc = datetime.now(timezone.utc)
    existing_inactive = (
        db.query(AlertSubscriber)
        .filter(
            AlertSubscriber.phone_number == normalized_phone,
            AlertSubscriber.ward_id == resolved_ward_id,
            AlertSubscriber.is_active == False,
        )
        .first()
    )

    is_new = True
    if existing_inactive:
        existing_inactive.is_active = True
        existing_inactive.channel = channel.value
        existing_inactive.subscribed_at = now_utc
        existing_inactive.consent_confirmed_at = now_utc
        subscriber = existing_inactive
        is_new = False
    else:
        subscriber = AlertSubscriber(
            phone_number=normalized_phone,
            ward_id=resolved_ward_id,
            channel=channel.value,
            subscribed_at=now_utc,
            is_active=True,
            consent_confirmed_at=now_utc,
            last_alert_sent_at=None,
        )
        db.add(subscriber)

    db.commit()

    # 6. Immediately send double opt-in confirmation message via existing sender
    if channel == SubscriptionChannel.WHATSAPP:
        confirm_msg = (
            f"🚨 *SIH26083: EXTREME HEATWAVE EARLY WARNING*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *STATUS:* ✅ SUBSCRIPTION CONFIRMED\n\n"
            f"📍 *Jurisdiction:* {resolved_ward_name} [{resolved_ward_id}]\n"
            f"⏱️ *Monitoring:* Active 24/7 Real-Time\n"
            f"🔔 *Tracking SID:* #WA-{normalized_phone[-6:]}-{resolved_ward_id}\n\n"
            f"📋 *MONITORING SCOPE:*\n"
            f"• Real-time WBGT & Human Thermal Stress Index\n"
            f"• Automated Code Red / Orange Hazard Warnings\n"
            f"• Demographic & Vulnerability Cohort Advisories\n\n"
            f"💧 *Immediate Preparedness Actions:*\n"
            f"• Maintain ORS hydration and carry water outdoors\n"
            f"• Cease strenuous labor during peak hours (11:30 AM - 4:00 PM)\n"
            f"• Nearest AMC Shelter: {resolved_ward_name} Community Health Centre\n\n"
            f"ℹ️ _Reply *STOP* anytime to unsubscribe._\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ _AMC & Gujarat State Disaster Management Authority_"
        )
    else:
        confirm_msg = (
            f"You're subscribed to heat alerts for {resolved_ward_name}. "
            "Reply STOP anytime to unsubscribe. - SIH26083 Heat Warning System"
        )

    if sender is None:
        if channel == SubscriptionChannel.WHATSAPP:
            sender = TwilioAlertSender(is_whatsapp=True)
        else:
            sender = TwilioAlertSender(is_whatsapp=False)

    try:
        dispatch_result = sender.send(to=normalized_phone, message=confirm_msg)
        delivery_status = "delivered" if dispatch_result.get("success") else "failed"
    except Exception as e:
        logger.error("Failed to send subscription confirmation to %s: %s", normalized_phone, e)
        delivery_status = "error"

    # 7. Log immutable consent audit record
    consent_entry = ConsentLog(
        phone_number=normalized_phone,
        ward_id=resolved_ward_id,
        action="SUBSCRIBE_OPT_IN",
        channel=channel.value,
        message_text=confirm_msg,
        delivery_status=delivery_status,
        recorded_at=now_utc,
    )
    db.add(consent_entry)
    db.commit()

    # Determine delivery mode and IDs
    is_live = bool(settings.twilio_account_sid and not settings.twilio_account_sid.startswith("mock_"))
    delivery_mode = "live" if is_live else "simulated"
    msg_id = dispatch_result.get("message_id") if isinstance(dispatch_result, dict) else None

    # Generate quick-action URLs for user device
    phone_digits = re.sub(r"[^\d]", "", normalized_phone)
    encoded_text = urllib.parse.quote(confirm_msg)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone_digits}&text={encoded_text}"
    sms_url = f"sms:{normalized_phone}?body={encoded_text}"

    return SubscribeResponse(
        success=True,
        message=f"Subscribed successfully to {resolved_ward_name}. Confirmation message dispatched.",
        phone_number=normalized_phone,
        ward_id=resolved_ward_id,
        ward_name=resolved_ward_name,
        channel=channel.value,
        is_new=is_new,
        delivery_mode=delivery_mode,
        delivery_status=delivery_status,
        message_id=msg_id,
        confirmation_text=confirm_msg,
        whatsapp_url=whatsapp_url,
        sms_url=sms_url,
    )


def unsubscribe(
    phone_number: str,
    ward_id: str = "ALL",
    db: Optional[Session] = None,
    sender: Optional[AlertSender] = None,
) -> UnsubscribeResponse:
    """Unsubscribe a phone number from heatwave alerts.

    Sets is_active=False for matching records, dispatches an opt-out confirmation message,
    and logs the action in ConsentLog.
    """
    if db is None:
        with SessionLocal() as session:
            return unsubscribe(
                phone_number=phone_number,
                ward_id=ward_id,
                db=session,
                sender=sender,
            )

    normalized_phone = normalize_and_validate_phone(phone_number)
    now_utc = datetime.now(timezone.utc)

    query = db.query(AlertSubscriber).filter(
        AlertSubscriber.phone_number == normalized_phone,
        AlertSubscriber.is_active == True,
    )
    if ward_id and ward_id.upper() != "ALL":
        query = query.filter(AlertSubscriber.ward_id == ward_id.strip().upper())

    matching_subs = query.all()
    deactivated_count = len(matching_subs)

    for sub in matching_subs:
        sub.is_active = False

    db.commit()

    # Check if subscriber was on WhatsApp channel
    has_whatsapp = any(s.channel == "whatsapp" for s in matching_subs)

    # Dispatch opt-out confirmation notice
    if has_whatsapp:
        unsub_msg = (
            f"🚨 *SIH26083: ALERT UN-REGISTRATION*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔕 *STATUS:* ✅ SUBSCRIPTION CANCELLED\n\n"
            f"📍 *Action:* Automated emergency heat alerts deactivated for {normalized_phone}.\n"
            f"⏱️ *Effective:* Immediate\n\n"
            f"ℹ️ _To resubscribe at any time, visit the portal or reply *START*._\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ _AMC & Gujarat State Disaster Management Authority_"
        )
    else:
        unsub_msg = (
            "You've been unsubscribed from SIH26083 Heat Warning alerts. "
            "Reply START anytime to resubscribe."
        )

    if sender is None:
        sender = TwilioAlertSender(is_whatsapp=has_whatsapp)

    try:
        dispatch_result = sender.send(to=normalized_phone, message=unsub_msg)
        status = "delivered" if dispatch_result.get("success") else "failed"
    except Exception as e:
        logger.warning("Could not dispatch unsubscribe notice to %s: %s", normalized_phone, e)
        status = "error"

    # Log in ConsentLog
    consent_entry = ConsentLog(
        phone_number=normalized_phone,
        ward_id=ward_id if ward_id.upper() != "ALL" else None,
        action="UNSUBSCRIBE_OPT_OUT",
        channel="sms",
        message_text=unsub_msg,
        delivery_status=status,
        recorded_at=now_utc,
    )
    db.add(consent_entry)
    db.commit()

    msg = (
        f"Successfully unsubscribed {normalized_phone} from {deactivated_count} alert subscription(s)."
        if deactivated_count > 0
        else f"No active alert subscriptions were found for {normalized_phone}."
    )

    phone_digits = re.sub(r"[^\d]", "", normalized_phone)
    encoded_unsub = urllib.parse.quote(unsub_msg)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone_digits}&text={encoded_unsub}"

    return UnsubscribeResponse(
        success=True,
        message=msg,
        phone_number=normalized_phone,
        deactivated_count=deactivated_count,
        confirmation_text=unsub_msg,
        whatsapp_url=whatsapp_url,
    )


def handle_stop_reply(
    phone_number: str,
    message_text: str,
    db: Optional[Session] = None,
    sender: Optional[AlertSender] = None,
) -> InboundWebhookResponse:
    """Process incoming carrier SMS/WhatsApp reply for automated STOP unsubscription compliance.

    Parameters
    ----------
    phone_number : str
        Sender's phone number.
    message_text : str
        Incoming message body.
    db : Optional[Session]
        Database session.
    sender : Optional[AlertSender]
        Sender instance.

    Returns
    -------
    InboundWebhookResponse
        Result indicating whether message was recognized and handled.
    """
    if db is None:
        with SessionLocal() as session:
            return handle_stop_reply(
                phone_number=phone_number,
                message_text=message_text,
                db=session,
                sender=sender,
            )

    raw_clean = (message_text or "").strip().lower()

    if raw_clean in STOP_KEYWORDS:
        unsub_res = unsubscribe(
            phone_number=phone_number,
            ward_id="ALL",
            db=db,
            sender=sender,
        )
        return InboundWebhookResponse(
            handled=True,
            action="UNSUBSCRIBED",
            detail=f"Inbound STOP processed: {unsub_res.message}",
        )

    if raw_clean in RESUME_KEYWORDS:
        normalized_phone = normalize_and_validate_phone(phone_number)
        return InboundWebhookResponse(
            handled=True,
            action="RESUBSCRIBE_PROMPT",
            detail=f"To resubscribe {normalized_phone}, visit the municipal dashboard to select your active ward.",
        )

    return InboundWebhookResponse(
        handled=False,
        action="IGNORED",
        detail=f"Incoming message '{message_text[:30]}' is not a compliance opt-in/opt-out keyword.",
    )
