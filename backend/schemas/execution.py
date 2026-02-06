"""Schemas for execution API payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from enums import ExecutionStatus


class ExecutionCreate(BaseModel):
    """Payload for launching a workflow execution."""

    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    input_data: dict | None = Field(default=None, description="Execution input")


class ExecutionResponse(BaseModel):
    """Response model for executions."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Execution ID", gt=0)
    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    status: ExecutionStatus = Field(default=..., description="Execution status")
    input_data: dict | None = Field(default=None, description="Execution input")
    output_data: dict | None = Field(default=None, description="Execution output")
    error: str | None = Field(default=None, description="Error message")
    started_at: datetime = Field(default=..., description="Started at")
    finished_at: datetime | None = Field(default=None, description="Finished at")
