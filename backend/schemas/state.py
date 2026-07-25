"""Schemas for typed durable workflow state."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from enums import StateHistoryOperation, StateScope
from schemas.artifact import NodeValuePayload

STATE_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class StateMutation(BaseModel):
    """Create or replace one typed state value."""

    value: NodeValuePayload
    expected_version: int | None = Field(
        default=None,
        ge=0,
        description=(
            "0 requires a missing key; a positive value requires an exact match"
        ),
    )
    ttl_seconds: int | None = Field(
        default=None,
        ge=1,
        le=31_536_000,
        description="Optional TTL up to one year; null stores the value indefinitely",
    )


class StateDelete(BaseModel):
    """Optional compare-and-delete request."""

    expected_version: int | None = Field(default=None, ge=1)


class StateEntryResponse(BaseModel):
    """Current typed value and optimistic-concurrency metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: StateScope
    key: str
    value: NodeValuePayload
    version: int
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StateHistoryResponse(BaseModel):
    """One immutable state mutation record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: StateScope
    key: str
    operation: StateHistoryOperation
    value: NodeValuePayload | None
    version: int
    expires_at: datetime | None
    execution_id: int | None
    created_at: datetime
