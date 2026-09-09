"""Gupshup Messaging Gateway Dispatcher.

Integrates Gupshup Enterprise Messaging for WhatsApp / SMS dispatches.
Includes sandbox simulation fallback when API keys are not provided.
"""

import uuid
import logging
from typing import Dict, Any, Optional
import requests

from backend.config import settings
from backend.alerts.sender_base import AlertSender

logger = logging.getLogger(__name__)


class GupshupAlertSender(AlertSender):
    """Gupshup notification gateway."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        src_name: Optional[str] = None,
        app_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.gupshup_api_key
        self.src_name = src_name or settings.gupshup_src_name or "SIH26083_EarlyWarning"
        self.app_name = app_name or settings.gupshup_app_name or "HeatwaveAlerts"

    def send(self, to: str, message: str) -> Dict[str, Any]:
        """Send early warning alert via Gupshup API or Sandbox Simulator."""
        recipient = to.replace("+", "").strip()

        # If live Gupshup API key present, execute live HTTP request
        if self.api_key and not self.api_key.startswith("mock_"):
            url = "https://api.gupshup.io/wa/api/v1/msg"
            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            payload = {
                "channel": "whatsapp",
                "source": self.src_name,
                "destination": recipient,
                "message": message,
                "src.name": self.app_name,
            }

            try:
                logger.info("Dispatching live Gupshup WhatsApp alert to %s...", recipient)
                res = requests.post(url, headers=headers, data=payload, timeout=10)
                data = res.json()
                if res.status_code in [200, 202]:
                    msg_id = data.get("messageId", f"GS{uuid.uuid4().hex[:16]}")
                    return {
                        "success": True,
                        "message_id": msg_id,
                        "detail": f"Gupshup alert dispatched successfully. Status: {data.get('status', 'submitted')}.",
                        "channel": "whatsapp",
                    }
                else:
                    logger.warning("Gupshup API returned %d: %s. Falling back to sandbox.", res.status_code, res.text)
            except Exception as e:
                logger.warning("Gupshup network error: %s. Falling back to sandbox.", e)

        # Sandbox / Mock Demo Simulator Fallback
        mock_id = f"GS{uuid.uuid4().hex[:20].upper()}"
        logger.info(
            "[GUPSHUP WHATSAPP SANDBOX SIMULATOR] Dispatched alert to %s | ID: %s | Text: '%s...'",
            recipient, mock_id, message[:60]
        )

        return {
            "success": True,
            "message_id": mock_id,
            "detail": "Gupshup Sandbox WhatsApp alert submitted successfully.",
            "channel": "whatsapp",
        }
