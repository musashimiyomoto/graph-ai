"""Async wrappers around standard-library IMAP and SMTP clients."""

import asyncio
import imaplib
import smtplib
import ssl
from contextlib import suppress
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.policy import default
from email.utils import parseaddr
from typing import Any

from constants import DEFAULT_TIMEOUT
from exceptions import EmailConnectionError


@dataclass(frozen=True)
class EmailConnectionConfig:
    """Decrypted connection values for one email account."""

    email_address: str
    username: str
    password: str
    imap_host: str
    imap_port: int
    imap_use_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    smtp_use_ssl: bool


@dataclass(frozen=True)
class InboundEmail:
    """Normalized incoming email used by the worker."""

    uid: int
    sender: str
    subject: str
    body: str


def _decode_header(value: str | None) -> str:
    """Decode an RFC 2047 header to readable text."""
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _message_body(message: Message) -> str:
    """Extract the preferred plain-text body, ignoring attachments."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                return _decode_payload(part)
        return ""

    return _decode_payload(message)


def _decode_payload(message: Message) -> str:
    """Decode one non-multipart message payload using its declared charset."""
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace").strip()
    raw = message.get_payload()
    return raw.strip() if isinstance(raw, str) else ""


def _parse_message(uid: int, raw: bytes) -> InboundEmail:
    """Parse one RFC email message into the worker's normalized shape."""
    message = message_from_bytes(raw, policy=default)
    sender = parseaddr(message.get("From", ""))[1]
    return InboundEmail(
        uid=uid,
        sender=sender,
        subject=_decode_header(message.get("Subject")),
        body=_message_body(message),
    )


def _require_ok(status: str, message: str) -> None:
    """Raise a channel error when an IMAP command did not succeed."""
    if status != "OK":
        raise EmailConnectionError(message=message)


def _fetch_messages_sync(
    config: EmailConnectionConfig, last_uid: int
) -> list[InboundEmail]:
    """Fetch messages with an IMAP UID greater than the saved offset."""
    client_class = imaplib.IMAP4_SSL if config.imap_use_ssl else imaplib.IMAP4
    client: Any | None = None
    try:
        client = client_class(
            host=config.imap_host,
            port=config.imap_port,
            timeout=DEFAULT_TIMEOUT,
        )
        client.login(config.username, config.password)
        status, _ = client.select("INBOX", readonly=True)
        _require_ok(status, "Unable to select the IMAP inbox")
        status, search_data = client.uid("search", "UID", f"{last_uid + 1}:*")
        _require_ok(status, "Unable to search the IMAP inbox")
        messages: list[InboundEmail] = []
        if search_data:
            for uid_raw in search_data[0].split():
                uid = int(uid_raw)
                status, fetch_data = client.uid("fetch", uid_raw, "(RFC822)")
                if status != "OK" or not fetch_data:
                    continue
                raw = next(
                    (
                        item[1]
                        for item in fetch_data
                        if isinstance(item, tuple)
                        and len(item) > 1
                        and isinstance(item[1], bytes)
                    ),
                    None,
                )
                if raw is None:
                    continue
                messages.append(_parse_message(uid, raw))
    except EmailConnectionError:
        raise
    except (imaplib.IMAP4.error, OSError, ValueError) as exc:
        raise EmailConnectionError from exc
    else:
        return messages
    finally:
        if client is not None:
            with suppress(imaplib.IMAP4.error, OSError):
                client.logout()


async def fetch_messages(
    config: EmailConnectionConfig, last_uid: int
) -> list[InboundEmail]:
    """Fetch new email without blocking the worker event loop."""
    return await asyncio.to_thread(_fetch_messages_sync, config, last_uid)


def _send_email_sync(
    config: EmailConnectionConfig, recipient: str, subject: str, text: str
) -> None:
    """Send one message over SMTP."""
    client: Any | None = None
    try:
        message = EmailMessage()
        message["From"] = config.email_address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)

        if config.smtp_use_ssl:
            client = smtplib.SMTP_SSL(
                host=config.smtp_host,
                port=config.smtp_port,
                timeout=DEFAULT_TIMEOUT,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(
                host=config.smtp_host,
                port=config.smtp_port,
                timeout=DEFAULT_TIMEOUT,
            )
        client.ehlo()
        if config.smtp_use_tls:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        client.login(config.username, config.password)
        client.send_message(message)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        raise EmailConnectionError from exc
    finally:
        if client is not None:
            with suppress(smtplib.SMTPException, OSError):
                client.quit()


async def send_email(
    config: EmailConnectionConfig, recipient: str, subject: str, text: str
) -> None:
    """Send email without blocking the worker event loop."""
    await asyncio.to_thread(_send_email_sync, config, recipient, subject, text)
