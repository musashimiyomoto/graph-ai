"""Email transport integration unit tests."""

from email.message import EmailMessage
from typing import Any

import pytest

import integrations.email as email_integration
from exceptions import EmailConnectionError
from integrations.email import EmailConnectionConfig, fetch_messages, send_email

_MESSAGE_UID = 42
_CONNECTION_ERROR = "connection refused"


def _config() -> EmailConnectionConfig:
    """Build transport settings used by the fake clients."""
    return EmailConnectionConfig(
        email_address="support@example.com",
        username="support@example.com",
        password="app-password",  # noqa: S106 - synthetic test credential
        imap_host="imap.example.com",
        imap_port=993,
        imap_use_ssl=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_use_tls=True,
        smtp_use_ssl=False,
    )


class _FakeImap:
    """Minimal successful IMAP client."""

    def __init__(self, **kwargs: object) -> None:
        """Record constructor arguments."""
        self.kwargs = kwargs

    def login(self, username: str, password: str) -> None:
        """Accept fake credentials."""
        if not username or not password:
            pytest.fail("Expected IMAP credentials")

    def select(self, mailbox: str, *, readonly: bool) -> tuple[str, list[bytes]]:
        """Select the fake inbox."""
        if mailbox != "INBOX" or not readonly:
            pytest.fail("Expected a read-only INBOX selection")
        return "OK", [b"1"]

    def uid(self, command: str, *args: object) -> tuple[str, list[Any]]:
        """Return one RFC message from UID search/fetch calls."""
        if command == "search":
            if args != ("UID", "42:*"):
                pytest.fail(f"Unexpected UID search: {args}")
            return "OK", [b"42"]
        if command == "fetch":
            message = EmailMessage()
            message["From"] = "Customer <customer@example.com>"
            message["Subject"] = "=?utf-8?b?0J/QvtC80L7RidGM?="
            message.set_content("My order is late")
            return "OK", [(b"42 (RFC822)", message.as_bytes())]
        pytest.fail(f"Unexpected IMAP command: {command}")

    def logout(self) -> None:
        """Close the fake connection."""


async def test_fetch_messages_parses_headers_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IMAP messages are normalized and RFC 2047 headers are decoded."""
    monkeypatch.setattr(email_integration.imaplib, "IMAP4_SSL", _FakeImap)

    messages = await fetch_messages(_config(), last_uid=41)

    if len(messages) != 1:
        pytest.fail(f"Expected one message, got {len(messages)}")
    message = messages[0]
    if (
        message.uid != _MESSAGE_UID
        or message.sender != "customer@example.com"
        or message.subject != "Помощь"
        or message.body != "My order is late"
    ):
        pytest.fail(f"Unexpected parsed message: {message}")


async def test_fetch_messages_wraps_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An IMAP constructor failure is exposed as a channel error."""

    def _fail_connect(**kwargs: object) -> None:
        del kwargs
        raise OSError(_CONNECTION_ERROR)

    monkeypatch.setattr(email_integration.imaplib, "IMAP4_SSL", _fail_connect)

    with pytest.raises(EmailConnectionError):
        await fetch_messages(_config(), last_uid=0)


async def test_send_email_wraps_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An SMTP constructor failure is exposed as a channel error."""

    def _fail_connect(**kwargs: object) -> None:
        del kwargs
        raise OSError(_CONNECTION_ERROR)

    monkeypatch.setattr(email_integration.smtplib, "SMTP", _fail_connect)

    with pytest.raises(EmailConnectionError):
        await send_email(
            _config(),
            recipient="customer@example.com",
            subject="Re: Need help",
            text="Resolved",
        )
