"""Common AlertSender Interface for SIH26083 Alert Dispatchers.

Defines the contract implemented by Twilio, Gupshup, and Webhook dispatchers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AlertSender(ABC):
    """Abstract base class for all notification dispatch gateways."""

    @abstractmethod
    def send(self, to: str, message: str) -> Dict[str, Any]:
        """Dispatch early warning message to recipient phone number or address.

        Parameters
        ----------
        to : str
            Recipient identifier in E.164 phone format (e.g. '+919876543210').
        message : str
            Actionable heat advisory message text.

        Returns
        -------
        Dict[str, Any]
            Status dictionary containing:
            - success: bool
            - message_id: str
            - detail: str
            - channel: str
        """
        pass
