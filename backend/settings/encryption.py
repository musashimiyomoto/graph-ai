"""Encryption settings."""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings
from settings.environment import INSECURE_KEY_ENVIRONMENTS


class EncryptionSettings(BaseSettings):
    """Configuration for symmetric secret encryption (Fernet)."""

    model_config = SettingsConfigDict(env_prefix="encryption_")

    environment: str = Field(
        default="local",
        title="Environment",
        validation_alias="ENVIRONMENT",
    )
    # Dev-only key, usable ONLY when ENVIRONMENT is local/test (enforced below).
    # Any other environment must set ENCRYPTION_SECRET_KEY to a real urlsafe
    # base64-encoded 32-byte Fernet key.
    secret_key: str = Field(
        default="ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=",
        title="Fernet secret key",
    )

    @model_validator(mode="after")
    def _require_real_key_outside_dev(self) -> Self:
        """Fail fast unless a real key is set outside local/test (secure default).

        Returns:
            The validated settings instance.

        Raises:
            ValueError: If the default key is used outside local/test.

        """
        default_key = type(self).model_fields["secret_key"].default
        if (
            self.secret_key == default_key
            and self.environment.lower() not in INSECURE_KEY_ENVIRONMENTS
        ):
            message = (
                "ENCRYPTION_SECRET_KEY must be set to a non-default value unless "
                "ENVIRONMENT is 'local' or 'test'"
            )
            raise ValueError(message)

        return self


encryption_settings = EncryptionSettings()
