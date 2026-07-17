"""Thin clients for third-party integrations."""

from integrations.email import (
    EmailConnectionConfig,
    InboundEmail,
    fetch_messages,
    send_email,
)
from integrations.webhook import send_webhook

__all__ = [
    "EmailConnectionConfig",
    "InboundEmail",
    "fetch_messages",
    "send_email",
    "send_webhook",
]
