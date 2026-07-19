"""Auth-related API schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginCreate(BaseModel):
    """Login payload."""

    email: EmailStr = Field(default=..., description="Email of the user")
    password: str = Field(default=..., description="Password of the user")


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str = Field(default=..., description="Access token")
    token_type: str = Field(default=..., description="Token type")


class AuthSessionResponse(BaseModel):
    """Public metadata for one revocable login session."""

    id: int
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    user_agent: str | None = None
    ip_address: str | None = None
    current: bool = False


class EmailActionRequest(BaseModel):
    """Request an account-security email without revealing account existence."""

    email: EmailStr = Field(default=..., description="Account email address")


class TokenActionRequest(BaseModel):
    """Consume an opaque one-time account action token."""

    token: str = Field(default=..., min_length=32, max_length=256)


class PasswordResetRequest(TokenActionRequest):
    """Choose a new password using a password recovery token."""

    new_password: str = Field(default=..., min_length=8, max_length=72)


class PasswordChangeRequest(BaseModel):
    """Change the password for an authenticated account."""

    current_password: str = Field(default=..., min_length=1, max_length=72)
    new_password: str = Field(default=..., min_length=8, max_length=72)
