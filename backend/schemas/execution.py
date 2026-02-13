"""Schemas for execution API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import ExecutionStatus


class ExecutionInputPayload(BaseModel):
    """Input payload for workflow execution."""

    value: str = Field(default=..., description="Text input value")


class ExecutionCreate(BaseModel):
    """Payload for launching a workflow execution."""

    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    input_data: ExecutionInputPayload = Field(
        default=...,
        description="Execution input",
    )


class ExecutionOutputPayload(BaseModel):
    """Output payload for workflow execution."""

    value: str = Field(default=..., description="Text output value")


class ExecutionGraphContext(BaseModel):
    """Validated graph context used by execution usecase."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    input_node_id: int = Field(default=..., description="Input node ID", gt=0)
    output_node_id: int = Field(default=..., description="Output node ID", gt=0)
    nodes_by_id: dict[int, Any] = Field(default=..., description="Nodes map")
    outbound: dict[int, list[int]] = Field(default=..., description="Outbound edges")
    inbound: dict[int, list[int]] = Field(default=..., description="Inbound edges")
    topological_order: list[int] = Field(default=..., description="Topological order")


class ExecutionResponse(BaseModel):
    """Response model for executions."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Execution ID", gt=0)
    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    status: ExecutionStatus = Field(default=..., description="Execution status")
    input_data: ExecutionInputPayload | None = Field(
        default=None,
        description="Execution input",
    )
    output_data: dict[str, Any] | None = Field(
        default=None, description="Execution output"
    )
    error: str | None = Field(default=None, description="Error message")
    started_at: datetime = Field(default=..., description="Started at")
    finished_at: datetime | None = Field(default=None, description="Finished at")
