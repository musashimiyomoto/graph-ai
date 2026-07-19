"""Account email delivery settings."""

from typing import Self

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings
from settings.environment import INSECURE_KEY_ENVIRONMENTS


class AuthEmailSettings(BaseSettings):
    """SMTP and link settings for account-security emails."""

    model_config = SettingsConfigDict(env_prefix="auth_email_")

    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: EmailStr = "noreply@example.com"
    frontend_url: str = "http://localhost:3000"
    verification_expire_hours: int = Field(default=24, ge=1, le=168)
    password_reset_expire_minutes: int = Field(default=60, ge=5, le=1440)

    @model_validator(mode="after")
    def _validate_delivery(self) -> Self:
        """Require a usable SMTP configuration outside local/test."""
        if self.smtp_use_tls and self.smtp_use_ssl:
            message = (
                "AUTH_EMAIL_SMTP_USE_TLS and AUTH_EMAIL_SMTP_USE_SSL are exclusive"
            )
            raise ValueError(message)
        if bool(self.smtp_username) != bool(self.smtp_password):
            message = (
                "AUTH_EMAIL_SMTP_USERNAME and AUTH_EMAIL_SMTP_PASSWORD "
                "must be set together"
            )
            raise ValueError(message)
        if (
            not self.smtp_host
            and self.environment.lower() not in INSECURE_KEY_ENVIRONMENTS
        ):
            message = "AUTH_EMAIL_SMTP_HOST must be set outside local/test"
            raise ValueError(message)
        return self


auth_email_settings = AuthEmailSettings()
