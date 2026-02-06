"""Schemas for workflow API payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreate(BaseModel):
    """Payload for creating a workflow."""

    name: str = Field(default=..., description="Workflow name")


class WorkflowUpdate(BaseModel):
    """Payload for updating a workflow."""

    name: str | None = Field(default=None, description="Workflow name")


class WorkflowResponse(BaseModel):
    """Response model for workflows."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Workflow ID", gt=0)
    owner_id: int = Field(default=..., description="Owner user ID", gt=0)
    name: str = Field(default=..., description="Workflow name")
    created_at: datetime = Field(default=..., description="Created at")
    updated_at: datetime = Field(default=..., description="Updated at")
