"""Early warning notification dispatcher stub module (Day 7 Scope).

Dispatches SMS and WhatsApp alerts to civic emergency coordinators, hospital heads,
and outdoor labor unions when a ward crosses dangerous heat stress thresholds.
Supported backends: Twilio (SMS), Gupshup (WhatsApp/SMS).
"""

import logging
from typing import Optional
from backend.config import settings
from backend.models import AlertPayload if "AlertPayload" in locals() else None
from backend.models import AlertRequest, AlertResponse, AlertChannel

logger = logging.getLogger(__name__)


def send_sms_alert(
    phone_number: str,
    ward_id: str,
    risk_level: str,
    message: str
) -> AlertResponse:
    """Dispatch an SMS alert via Twilio / Gupshup gateway.

    Parameters
    ----------
    phone_number : str
        Recipient phone number in E.164 format (e.g. +91XXXXXXXXXX).
    ward_id : str
        Ward triggering the heat threshold.
    risk_level : str
        Heat stress risk tier (e.g. DANGER, EXTREME_DANGER).
    message : str
        Pre-formatted SMS advisory text.

    Returns
    -------
    AlertResponse
        Confirmation payload with message delivery status.

    Notes
    -----
    Full Twilio / Gupshup client dispatch will be implemented in Day 7.
    """
    logger.info("Alert requested for ward %s to %s (Stub)", ward_id, phone_number)
    return AlertResponse(
        success=False,
        ward_id=ward_id,
        recipient_phone=phone_number,
        channel=AlertChannel.SMS,
        detail="Alert system is stubbed for Day 1; will be fully implemented in Day 7."
    )
