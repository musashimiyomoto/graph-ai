"""Schemas for Telegram bot API payloads."""

from pydantic import BaseModel, ConfigDict, Field


class TelegramBotCreate(BaseModel):
    """Payload for creating a Telegram bot."""

    name: str = Field(default=..., description="Bot display name")
    bot_token: str = Field(
        default=..., description="Telegram bot token (write-only)", min_length=1
    )


class TelegramBotUpdate(BaseModel):
    """Payload for updating a Telegram bot."""

    name: str | None = Field(default=None, description="Bot display name")
    bot_token: str | None = Field(
        default=None, description="Telegram bot token (write-only)", min_length=1
    )
    enabled: bool | None = Field(default=None, description="Whether polling is active")


class TelegramBotResponse(BaseModel):
    """Response model for Telegram bots.

    ``bot_token`` is intentionally never returned: it is write-only, same as an
    LLM provider's ``api_key``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Bot ID", gt=0)
    user_id: int = Field(default=..., description="Owner user ID", gt=0)
    connection_id: int = Field(
        default=..., description="Credential connection ID", gt=0
    )
    name: str = Field(default=..., description="Bot display name")
    enabled: bool = Field(default=..., description="Whether polling is active")
