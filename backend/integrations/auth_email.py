"""Delivery of email verification and password recovery links."""

import asyncio
import logging
import smtplib
import ssl
from contextlib import suppress
from email.message import EmailMessage
from typing import Protocol
from urllib.parse import urlencode

from constants import DEFAULT_TIMEOUT
from exceptions import EmailConnectionError
from settings import auth_email_settings

logger = logging.getLogger(__name__)


class AuthEmailSender(Protocol):
    """Port used by authentication flows to deliver account links."""

    async def send_verification(self, recipient: str, token: str) -> None:
        """Send an email verification link."""

    async def send_password_reset(self, recipient: str, token: str) -> None:
        """Send a password reset link."""


class SMTPAuthEmailSender:
    """SMTP-backed account email sender with a local log-only fallback."""

    async def send_verification(self, recipient: str, token: str) -> None:
        """Send an email verification link."""
        link = self._frontend_link("verify_email_token", token)
        await self._send(
            recipient,
            "Verify your Graph AI email",
            "Verify your email to activate your Graph AI account:\n\n"
            f"{link}\n\nThis link expires in "
            f"{auth_email_settings.verification_expire_hours} hours.",
        )

    async def send_password_reset(self, recipient: str, token: str) -> None:
        """Send a password reset link."""
        link = self._frontend_link("reset_password_token", token)
        await self._send(
            recipient,
            "Reset your Graph AI password",
            "Use this link to choose a new Graph AI password:\n\n"
            f"{link}\n\nThis link expires in "
            f"{auth_email_settings.password_reset_expire_minutes} minutes. "
            "If you did not request this, you can ignore this email.",
        )

    @staticmethod
    def _frontend_link(parameter: str, token: str) -> str:
        """Build a link understood by the single-page auth screen."""
        query = urlencode({parameter: token})
        return f"{auth_email_settings.frontend_url.rstrip('/')}/?{query}"

    async def _send(self, recipient: str, subject: str, text: str) -> None:
        """Send over SMTP or expose the link in local logs."""
        if not auth_email_settings.smtp_host:
            logger.info(
                "Account email delivery skipped in local mode",
                extra={"recipient": recipient, "subject": subject, "body": text},
            )
            return
        await asyncio.to_thread(self._send_sync, recipient, subject, text)

    @staticmethod
    def _send_sync(recipient: str, subject: str, text: str) -> None:
        """Perform the blocking SMTP exchange."""
        smtp_host = auth_email_settings.smtp_host
        if smtp_host is None:
            return
        message = EmailMessage()
        message["From"] = str(auth_email_settings.from_address)
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)

        if auth_email_settings.smtp_use_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                smtp_host,
                auth_email_settings.smtp_port,
                timeout=DEFAULT_TIMEOUT,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(
                smtp_host,
                auth_email_settings.smtp_port,
                timeout=DEFAULT_TIMEOUT,
            )
        try:
            client.ehlo()
            if auth_email_settings.smtp_use_tls:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if auth_email_settings.smtp_username and auth_email_settings.smtp_password:
                client.login(
                    auth_email_settings.smtp_username,
                    auth_email_settings.smtp_password,
                )
            client.send_message(message)
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            raise EmailConnectionError(
                message="Unable to deliver account email"
            ) from exc
        finally:
            with suppress(smtplib.SMTPException, OSError):
                client.quit()
