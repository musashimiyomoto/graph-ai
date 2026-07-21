"""Public web-chat API schemas."""

from pydantic import BaseModel, Field


class WebChatMessage(BaseModel):
    """One visitor message sent through an embedded web chat."""

    value: str = Field(default=..., min_length=1, max_length=50_000)
    event_id: str = Field(default=..., min_length=1, max_length=255)
    conversation_id: str = Field(default=..., min_length=1, max_length=998)
    locale: str | None = Field(default=None, max_length=35)
