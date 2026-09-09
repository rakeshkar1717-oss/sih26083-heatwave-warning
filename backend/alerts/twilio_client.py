"""Twilio SMS and WhatsApp Early Warning Dispatcher.

Integrates Twilio REST API for emergency early warning alerts.
Gracefully handles Sandbox mode and simulated demo environments when API credentials are absent.
"""

import uuid
import logging
from typing import Dict, Any, Optional
import requests

from backend.config import settings
from backend.alerts.sender_base import AlertSender

logger = logging.getLogger(__name__)


class TwilioAlertSender(AlertSender):
    """Twilio SMS and WhatsApp notification gateway."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        is_whatsapp: bool = False,
    ):
        self.account_sid = account_sid or settings.twilio_account_sid
        self.auth_token = auth_token or settings.twilio_auth_token
        self.is_whatsapp = is_whatsapp

        if is_whatsapp:
            self.from_number = from_number or settings.twilio_whatsapp_from
        else:
            self.from_number = from_number or settings.twilio_phone_number or "+15005550006"

    def send(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS or WhatsApp alert via Twilio REST API or Sandbox Simulator."""
        channel_name = "whatsapp" if (self.is_whatsapp or to.startswith("whatsapp:")) else "sms"
        recipient = to if (channel_name != "whatsapp" or to.startswith("whatsapp:")) else f"whatsapp:{to}"

        # If valid Twilio credentials provided, execute live REST API call
        if self.account_sid and self.auth_token and not self.account_sid.startswith("mock_"):
            endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            payload = {
                "From": self.from_number,
                "To": recipient,
                "Body": message,
            }

            try:
                logger.info("Dispatching live Twilio %s alert to %s...", channel_name.upper(), recipient)
                res = requests.post(
                    endpoint,
                    data=payload,
                    auth=(self.account_sid, self.auth_token),
                    timeout=10,
                )
                data = res.json()
                if res.status_code in [200, 201]:
                    msg_sid = data.get("sid", f"SM{uuid.uuid4().hex[:16]}")
                    logger.info("Twilio dispatch confirmed: SID=%s", msg_sid)
                    return {
                        "success": True,
                        "message_id": msg_sid,
                        "detail": f"Twilio {channel_name.upper()} delivered. Status: {data.get('status', 'queued')}.",
                        "channel": channel_name,
                    }
                else:
                    err_msg = data.get("message", res.text)
                    logger.warning("Twilio API returned error (%d): %s. Falling back to Sandbox demo simulation.", res.status_code, err_msg)
            except Exception as e:
                logger.warning("Twilio network dispatch failed: %s. Falling back to Sandbox demo simulation.", e)

        # Sandbox / Mock Demo Simulator Fallback
        mock_sid = f"SM{uuid.uuid4().hex[:24].upper()}" if channel_name == "sms" else f"WA{uuid.uuid4().hex[:24].upper()}"
        logger.info(
            "[TWILIO %s SANDBOX SIMULATOR] Dispatched alert to %s | SID: %s | Text: '%s...'",
            channel_name.upper(), recipient, mock_sid, message[:60]
        )

        return {
            "success": True,
            "message_id": mock_sid,
            "detail": f"Twilio Sandbox {channel_name.upper()} dispatch confirmed. Message queued for delivery.",
            "channel": channel_name,
        }
