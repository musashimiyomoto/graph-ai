"""Public web-chat API schemas."""

from pydantic import BaseModel, Field

from schemas.execution import ExecutionResponse


class WebChatMessage(BaseModel):
    """One visitor message sent through an embedded web chat."""

    value: str = Field(default=..., min_length=1, max_length=50_000)
    event_id: str = Field(default=..., min_length=1, max_length=255)
    session_id: str | None = Field(default=None, min_length=16, max_length=64)
    locale: str | None = Field(default=None, max_length=35)


class WebChatExecutionResponse(ExecutionResponse):
    """Public execution response carrying its opaque conversation session."""

    session_id: str = Field(min_length=16, max_length=64)
