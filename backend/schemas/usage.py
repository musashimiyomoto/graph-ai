"""Schemas for usage and audit API payloads."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class QuotaStatus(BaseModel):
    """A single quota dimension: its limit, current usage, and remaining."""

    limit: int = Field(default=..., description="Limit for the window (0 = unlimited)")
    used: int = Field(default=..., description="Amount consumed in the window")
    remaining: int | None = Field(
        default=None,
        description="Remaining allowance, or null when the dimension is unlimited",
    )


class UsageSummaryResponse(BaseModel):
    """A tenant's usage for the current window plus its quota status."""

    period_start: date = Field(default=..., description="Window start (UTC day)")
    executions: QuotaStatus = Field(default=..., description="Execution-count quota")
    tokens: QuotaStatus = Field(default=..., description="Token quota")


class AuditLogResponse(BaseModel):
    """Response model for one audit log row."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Audit log ID", gt=0)
    user_id: int = Field(default=..., description="Acting user ID", gt=0)
    action: str = Field(default=..., description="Action name")
    entity_type: str = Field(default=..., description="Affected entity type")
    entity_id: int | None = Field(default=None, description="Affected entity ID")
    metadata: dict = Field(
        default_factory=dict,
        validation_alias="audit_metadata",
        description="Extra structured context",
    )
    created_at: datetime = Field(default=..., description="When the action occurred")
