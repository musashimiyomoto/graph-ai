"""Thin clients for third-party integrations."""

from integrations.email import (
    EmailConnectionConfig,
    InboundEmail,
    fetch_messages,
    send_email,
)

__all__ = [
    "EmailConnectionConfig",
    "InboundEmail",
    "fetch_messages",
    "send_email",
]
