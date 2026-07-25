"""Public web-chat API schemas."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from schemas.execution import ExecutionResponse


class WebChatMessage(BaseModel):
    """One visitor message sent through an embedded web chat."""

    value: str = Field(default=..., min_length=1, max_length=50_000)
    event_id: str = Field(default=..., min_length=1, max_length=255)
    session_id: str | None = Field(default=None, min_length=16, max_length=64)
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=998,
        description="Deprecated client-generated conversation identifier",
    )
    locale: str | None = Field(default=None, max_length=35)

    @model_validator(mode="after")
    def validate_session_identity(self) -> Self:
        """Reject ambiguous requests that supply both identity mechanisms."""
        if self.session_id is not None and self.conversation_id is not None:
            message = "Use session_id or conversation_id, not both"
            raise ValueError(message)
        return self


class WebChatExecutionResponse(ExecutionResponse):
    """Public execution response carrying its opaque conversation session."""

    session_id: str = Field(min_length=16, max_length=64)
