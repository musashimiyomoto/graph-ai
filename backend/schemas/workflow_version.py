"""Schemas for workflow version API payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowVersionResponse(BaseModel):
    """Response model for a workflow version snapshot (metadata only)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Version ID", gt=0)
    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    version: int = Field(default=..., description="Per-workflow version number")
    created_at: datetime = Field(default=..., description="Snapshot creation time")
