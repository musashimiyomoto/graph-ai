"""Schemas for workflow API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import NodeType


class WorkflowCreate(BaseModel):
    """Payload for creating a workflow."""

    name: str = Field(
        default=..., description="Workflow name", min_length=1, max_length=200
    )


class WorkflowGraphNode(BaseModel):
    """A portable node within a workflow graph transfer payload.

    Deliberately excludes ``id``/``workflow_id`` — a transferred graph (export
    file, duplicate, template) always creates fresh nodes, so callers must not
    be able to reference or collide with existing IDs.
    """

    type: NodeType = Field(default=..., description="Node type")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Node configuration data"
    )
    position_x: float = Field(default=0.0, description="X position on canvas")
    position_y: float = Field(default=0.0, description="Y position on canvas")


class WorkflowGraphEdge(BaseModel):
    """A portable edge within a workflow graph transfer payload.

    References nodes by their (0-based) position in the transfer payload's
    ``nodes`` list rather than a database ID, since the graph's own node IDs
    don't exist yet at import time and an export's node IDs are meaningless
    to a different workflow/account.
    """

    source_index: int = Field(
        default=..., description="Index of the source node in `nodes`", ge=0
    )
    target_index: int = Field(
        default=..., description="Index of the target node in `nodes`", ge=0
    )
    source_handle: str | None = Field(
        default=None, description="Named output handle on the source node"
    )


class WorkflowGraphTransfer(BaseModel):
    """A whole graph in the shape shared by export/import/duplicate/templates."""

    nodes: list[WorkflowGraphNode] = Field(default_factory=list)
    edges: list[WorkflowGraphEdge] = Field(default_factory=list)


class WorkflowExportResponse(BaseModel):
    """Response model for a workflow export."""

    name: str = Field(default=..., description="Workflow name")
    graph: WorkflowGraphTransfer = Field(default=..., description="Portable graph")


class WorkflowImportRequest(BaseModel):
    """Payload for importing a workflow from an export file."""

    name: str = Field(
        default=..., description="Workflow name", min_length=1, max_length=200
    )
    graph: WorkflowGraphTransfer = Field(default=..., description="Portable graph")


class WorkflowUpdate(BaseModel):
    """Payload for updating a workflow."""

    name: str | None = Field(
        default=None, description="Workflow name", min_length=1, max_length=200
    )


class WorkflowResponse(BaseModel):
    """Response model for workflows."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Workflow ID", gt=0)
    owner_id: int = Field(default=..., description="Owner user ID", gt=0)
    name: str = Field(default=..., description="Workflow name")
    created_at: datetime = Field(default=..., description="Created at")
    updated_at: datetime = Field(default=..., description="Updated at")
