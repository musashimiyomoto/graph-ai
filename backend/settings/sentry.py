"""Sentry error-tracking settings."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class SentrySettings(BaseSettings):
    """Configuration for Sentry error tracking.

    Disabled by default: with no ``SENTRY_DSN`` set, initialization is a no-op,
    so a local/CI run needs no Sentry account. Set the DSN in a real deployment
    to start capturing errors from both the API and the worker process.
    """

    model_config = SettingsConfigDict(env_prefix="sentry_")

    dsn: str = Field(
        default="",
        validation_alias="SENTRY_DSN",
        title="Sentry DSN (empty = error tracking disabled)",
    )
    environment: str = Field(
        default="local",
        validation_alias="SENTRY_ENVIRONMENT",
        title="Environment tag reported to Sentry",
    )
    traces_sample_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        validation_alias="SENTRY_TRACES_SAMPLE_RATE",
        title="Performance tracing sample rate (0 = tracing off)",
    )

    @property
    def enabled(self) -> bool:
        """Whether a DSN is configured."""
        return bool(self.dsn)


sentry_settings = SentrySettings()
