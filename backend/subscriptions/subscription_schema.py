"""Pydantic schemas for Anonymous Phone/WhatsApp Alert Subscriptions.

Defines schemas for subscription signups, unsubscriptions, and inbound webhook messages.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SubscriptionChannel(str, Enum):
    """Supported delivery channels for automated alert subscriptions."""
    SMS = "sms"
    WHATSAPP = "whatsapp"


class SubscribeRequest(BaseModel):
    """Payload to subscribe a phone number to hyper-local heatwave alerts."""

    phone_number: str = Field(..., description="E.164 or 10-digit Indian phone number (e.g. '+919876543210' or '9876543210')")
    ward_id: Optional[str] = Field(default=None, description="Target municipal ward ID (e.g. 'AMD_01')")
    lat: Optional[float] = Field(default=None, description="Optional GPS latitude to resolve nearest ward")
    lon: Optional[float] = Field(default=None, description="Optional GPS longitude to resolve nearest ward")
    channel: SubscriptionChannel = Field(default=SubscriptionChannel.SMS, description="Preferred alert delivery channel")


class SubscribeResponse(BaseModel):
    """Confirmation response upon successful alert subscription."""

    success: bool
    message: str
    phone_number: str
    ward_id: str
    ward_name: str
    channel: str
    is_new: bool = True


class UnsubscribeRequest(BaseModel):
    """Payload to unsubscribe a phone number from heatwave alerts."""

    phone_number: str = Field(..., description="Phone number to unsubscribe")
    ward_id: Optional[str] = Field(default="ALL", description="Specific ward ID or 'ALL' to remove from all wards")


class UnsubscribeResponse(BaseModel):
    """Response returned upon processing an unsubscription request."""

    success: bool
    message: str
    phone_number: str
    deactivated_count: int


class InboundWebhookResponse(BaseModel):
    """Structured response from processing an inbound carrier webhook."""

    handled: bool
    action: str
    detail: str
