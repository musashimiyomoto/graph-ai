"""Public web-chat API schemas."""

from pydantic import BaseModel, Field


class WebChatMessage(BaseModel):
    """One visitor message sent through an embedded web chat."""

    value: str = Field(default=..., min_length=1, max_length=50_000)
