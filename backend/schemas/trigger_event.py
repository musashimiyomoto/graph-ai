"""Provider-neutral inbound trigger event schemas."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from enums import ExecutionSource, PortType
from schemas.artifact import NodeValuePayload


class TriggerActor(BaseModel):
    """Normalized sender identity supplied by an inbound channel."""

    id: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=320)
    address: str | None = Field(default=None, max_length=998)


class TriggerConversation(BaseModel):
    """Provider conversation and optional nested thread identifiers."""

    id: str = Field(default=..., min_length=1, max_length=998)
    thread_id: str | None = Field(default=None, max_length=998)


class TriggerEvent(BaseModel):
    """Versioned, provider-neutral event that caused one execution."""

    schema_version: Literal[1] = 1
    channel: ExecutionSource
    external_event_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Stable provider ID used to deduplicate inbound retries",
    )
    sender: TriggerActor | None = None
    conversation: TriggerConversation | None = None
    locale: str | None = Field(default=None, max_length=35)
    message: NodeValuePayload
    attachments: list[NodeValuePayload] = Field(default_factory=list, max_length=25)
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_retention: Literal["discard"] = "discard"

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        """Require an unambiguous timestamp; manual event IDs may be absent."""
        if self.occurred_at.tzinfo is None:
            message = "Trigger event occurred_at must be timezone-aware"
            raise ValueError(message)
        attachment_kinds = {
            PortType.FILE,
            PortType.IMAGE,
            PortType.AUDIO,
            PortType.VIDEO,
        }
        if any(item.kind not in attachment_kinds for item in self.attachments):
            message = "Trigger event attachments must contain artifact values"
            raise ValueError(message)
        return self
