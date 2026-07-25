"""Schemas for execution API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import ExecutionSource, ExecutionStatus, NodeType, PortCoercion
from schemas.artifact import NodeValuePayload
from schemas.trigger_event import TriggerEvent


class ExecutionInputPayload(BaseModel):
    """Input payload for workflow execution."""

    value: str = Field(
        default=...,
        description="Text input value",
        max_length=50_000,
    )


class ExecutionCreate(BaseModel):
    """Payload for launching a workflow execution."""

    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    input_data: ExecutionInputPayload = Field(
        default=...,
        description="Execution input",
    )
    version_id: int | None = Field(
        default=None,
        description="Run a specific workflow version; omit to snapshot the live graph",
        gt=0,
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
    outbound_edges: dict[
        int, list[tuple[int, str | None, str | None, PortCoercion | None]]
    ] = Field(default=..., description="Outbound edges with handles and coercion")
    inbound_edges: dict[
        int, list[tuple[int, str | None, str | None, PortCoercion | None]]
    ] = Field(default=..., description="Inbound edges with handles and coercion")
    topological_order: list[int] = Field(default=..., description="Topological order")


class ExecutionResponse(BaseModel):
    """Response model for executions."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Execution ID", gt=0)
    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    version_id: int | None = Field(
        default=None, description="Pinned workflow version ID"
    )
    status: ExecutionStatus = Field(default=..., description="Execution status")
    source: ExecutionSource = Field(default=..., description="What triggered this run")
    input_data: ExecutionInputPayload | None = Field(
        default=None,
        description="Execution input",
    )
    trigger_event: TriggerEvent = Field(
        default=...,
        description="Normalized event that caused this execution",
    )
    output_data: dict[str, Any] | None = Field(
        default=None, description="Execution output"
    )
    error: str | None = Field(default=None, description="Error message")
    approval_node_id: int | None = Field(
        default=None, description="Node currently awaiting approval"
    )
    approval_prompt: str | None = Field(
        default=None, description="Approval request shown to the owner"
    )
    approval_input: str | None = Field(
        default=None, description="Upstream value awaiting approval"
    )
    queue_job_id: str | None = Field(
        default=None, description="Current background job ID"
    )
    wait_until: datetime | None = Field(
        default=None, description="Next durable Delay checkpoint wake-up time"
    )
    prompt_tokens: int | None = Field(
        default=None, description="Total LLM prompt tokens across the run"
    )
    completion_tokens: int | None = Field(
        default=None, description="Total LLM completion tokens across the run"
    )
    total_tokens: int | None = Field(
        default=None, description="Total LLM tokens across the run"
    )
    started_at: datetime = Field(default=..., description="Started at")
    finished_at: datetime | None = Field(default=None, description="Finished at")


class NodeExecutionResponse(BaseModel):
    """Response model for a single node's result within an execution."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Node execution ID", gt=0)
    execution_id: int = Field(default=..., description="Parent execution ID", gt=0)
    node_id: int = Field(
        default=...,
        description="Executed node ID (not FK-enforced; the node may since "
        "be deleted from the live workflow)",
        gt=0,
    )
    node_type: NodeType | None = Field(
        default=None, description="Node type at execution time"
    )
    node_label: str | None = Field(
        default=None, description="Node label at execution time"
    )
    iteration: int | None = Field(
        default=None,
        description="Loop iteration index (0-based); None for a top-level node",
    )
    status: ExecutionStatus = Field(default=..., description="Node execution status")
    output_values: dict[str, NodeValuePayload] | None = Field(
        default=None,
        description="Typed node output envelopes keyed by output port name",
    )
    error: str | None = Field(default=None, description="Error message")
    prompt_tokens: int | None = Field(
        default=None, description="LLM prompt tokens, if this node called an LLM"
    )
    completion_tokens: int | None = Field(
        default=None, description="LLM completion tokens, if this node called an LLM"
    )
    total_tokens: int | None = Field(
        default=None, description="LLM total tokens, if this node called an LLM"
    )
    started_at: datetime = Field(default=..., description="Started at")
    finished_at: datetime | None = Field(default=None, description="Finished at")
    wait_until: datetime | None = Field(
        default=None, description="Delay checkpoint wake-up time"
    )
