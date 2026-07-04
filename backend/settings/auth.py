"""Authentication settings."""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings
from settings.environment import INSECURE_KEY_ENVIRONMENTS


class AuthSettings(BaseSettings):
    """Auth configuration loaded from environment."""

    model_config = SettingsConfigDict(env_prefix="auth_")

    environment: str = Field(
        default="local",
        title="Environment",
        validation_alias="ENVIRONMENT",
    )
    # Dev-only secret, usable ONLY when ENVIRONMENT is local/test (enforced below).
    secret_key: str = Field(default="secret", title="Secret key")
    algorithm: str = Field(default="HS256", title="Algorithm")
    access_token_expire_minutes: int = Field(
        default=30, title="Access token expire minutes"
    )
    token_type: str = Field(default="Bearer", title="Token type")

    @model_validator(mode="after")
    def _require_real_secret_outside_dev(self) -> Self:
        """Fail fast unless a real secret is set outside local/test (secure default).

        Returns:
            The validated settings instance.

        Raises:
            ValueError: If the default secret is used outside local/test.

        """
        default_secret = type(self).model_fields["secret_key"].default
        if (
            self.secret_key == default_secret
            and self.environment.lower() not in INSECURE_KEY_ENVIRONMENTS
        ):
            message = (
                "AUTH_SECRET_KEY must be set to a non-default value unless "
                "ENVIRONMENT is 'local' or 'test'"
            )
            raise ValueError(message)

        return self


auth_settings = AuthSettings()
