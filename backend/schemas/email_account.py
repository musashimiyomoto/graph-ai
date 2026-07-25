"""Schemas for email account API payloads."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class EmailAccountCreate(BaseModel):
    """Payload for creating an email account."""

    name: str = Field(default=..., min_length=1, max_length=128)
    email_address: EmailStr = Field(default=..., max_length=320)
    username: str = Field(default=..., min_length=1, max_length=320)
    password: str = Field(default=..., min_length=1, description="Write-only password")
    imap_host: str = Field(default=..., min_length=1, max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_use_ssl: bool = True
    smtp_host: str = Field(default=..., min_length=1, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    @model_validator(mode="after")
    def _validate_smtp_security(self) -> "EmailAccountCreate":
        """Reject mutually exclusive implicit TLS and STARTTLS modes."""
        if self.smtp_use_tls and self.smtp_use_ssl:
            message = "smtp_use_tls and smtp_use_ssl cannot both be enabled"
            raise ValueError(message)
        return self


class EmailAccountUpdate(BaseModel):
    """Payload for updating an email account."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    email_address: EmailStr | None = Field(default=None, max_length=320)
    username: str | None = Field(default=None, min_length=1, max_length=320)
    password: str | None = Field(default=None, min_length=1)
    imap_host: str | None = Field(default=None, min_length=1, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_use_ssl: bool | None = None
    smtp_host: str | None = Field(default=None, min_length=1, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_use_tls: bool | None = None
    smtp_use_ssl: bool | None = None
    enabled: bool | None = None


class EmailAccountResponse(BaseModel):
    """Email account response with credentials omitted."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., gt=0)
    user_id: int = Field(default=..., gt=0)
    connection_id: int = Field(default=..., gt=0)
    name: str
    email_address: EmailStr
    username: str
    imap_host: str
    imap_port: int
    imap_use_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    smtp_use_ssl: bool
    enabled: bool
