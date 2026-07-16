"""Per-tenant usage quota settings."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class QuotaSettings(BaseSettings):
    """Per-user usage quota limits, applied per rolling daily window.

    A limit of 0 means unlimited — the gate is skipped entirely, which is the
    default so an unconfigured deployment behaves exactly as before quotas
    existed.
    """

    model_config = SettingsConfigDict(env_prefix="quota_")

    max_executions_per_day: int = Field(
        default=0,
        ge=0,
        title="Max executions a user may start per day (0 = unlimited)",
    )
    max_tokens_per_day: int = Field(
        default=0,
        ge=0,
        title="Max LLM tokens a user may consume per day (0 = unlimited)",
    )
    window_seconds: int = Field(
        default=86_400,
        gt=0,
        title="Length of the quota window in seconds (default 1 day)",
    )

    @property
    def enabled(self) -> bool:
        """Whether any quota limit is configured."""
        return self.max_executions_per_day > 0 or self.max_tokens_per_day > 0


quota_settings = QuotaSettings()
