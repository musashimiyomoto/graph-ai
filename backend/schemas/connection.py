"""Schemas for unified encrypted connections and OAuth flows."""

from datetime import datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from enums import ConnectionAuthType, ConnectionStatus

_URL_FIELDS = (
    "authorization_url",
    "token_url",
    "revocation_url",
    "health_url",
)
_MAX_SCOPE_LENGTH = 256


class ConnectionCreate(BaseModel):
    """Create an API-key or OAuth 2.0 authorization-code connection."""

    name: str = Field(min_length=1, max_length=128)
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    auth_type: ConnectionAuthType
    scopes: list[str] = Field(default_factory=list, max_length=50)

    api_key: SecretStr | None = None
    header_name: str = Field(default="Authorization", min_length=1, max_length=128)
    prefix: str = Field(default="Bearer", max_length=64)

    authorization_url: str | None = Field(default=None, max_length=2048)
    token_url: str | None = Field(default=None, max_length=2048)
    revocation_url: str | None = Field(default=None, max_length=2048)
    health_url: str | None = Field(default=None, max_length=2048)
    client_id: str | None = Field(default=None, max_length=512)
    client_secret: SecretStr | None = None

    @field_validator(*_URL_FIELDS)
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        """Require configured endpoints to be absolute HTTP(S) URLs."""
        if value is not None and not value.startswith(("http://", "https://")):
            message = "Connection endpoint must start with http:// or https://"
            raise ValueError(message)
        return value

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        """Normalize, bound, and deduplicate OAuth scopes."""
        scopes: list[str] = []
        for item in value:
            scope = item.strip()
            if not scope or len(scope) > _MAX_SCOPE_LENGTH:
                message = "Connection scopes must contain 1 to 256 characters"
                raise ValueError(message)
            if scope not in scopes:
                scopes.append(scope)
        return scopes

    @model_validator(mode="after")
    def validate_auth_fields(self) -> Self:
        """Require exactly the credential fields needed by the auth protocol."""
        if self.auth_type is ConnectionAuthType.NONE:
            if (
                self.api_key is not None
                or self.authorization_url
                or self.token_url
                or self.revocation_url
                or self.client_id
                or self.client_secret
            ):
                message = "Credential-free connections cannot include secrets"
                raise ValueError(message)
            return self
        if self.auth_type is ConnectionAuthType.API_KEY:
            if self.api_key is None:
                message = "API-key connections require api_key"
                raise ValueError(message)
            if (
                self.authorization_url
                or self.token_url
                or self.revocation_url
                or self.client_id
                or self.client_secret
            ):
                message = "API-key connections cannot include OAuth endpoints"
                raise ValueError(message)
            return self
        if self.api_key is not None:
            message = "OAuth connections cannot include api_key"
            raise ValueError(message)
        if not self.authorization_url or not self.token_url or not self.client_id:
            message = (
                "OAuth connections require authorization_url, token_url, and client_id"
            )
            raise ValueError(message)
        return self


class ConnectionResponse(BaseModel):
    """Public connection metadata with no decrypted credential values."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    name: str
    provider: str
    auth_type: ConnectionAuthType
    status: ConnectionStatus
    config: dict
    scopes: list[str]
    has_credentials: bool
    token_expires_at: datetime | None
    last_used_at: datetime | None
    last_checked_at: datetime | None
    last_error: str | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectionOAuthStart(BaseModel):
    """Redirect URI for starting one OAuth authorization-code flow."""

    redirect_uri: str = Field(min_length=1, max_length=2048)

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, value: str) -> str:
        """Require an absolute browser callback URL."""
        if not value.startswith(("http://", "https://")):
            message = "OAuth redirect_uri must start with http:// or https://"
            raise ValueError(message)
        return value


class ConnectionOAuthStartResponse(BaseModel):
    """Provider authorization URL and state lifetime metadata."""

    authorization_url: str
    expires_at: datetime


class ConnectionOAuthCallbackResponse(BaseModel):
    """Minimal callback result safe for an unauthenticated browser window."""

    connection_id: int
    status: ConnectionStatus
