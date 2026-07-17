"""Schemas for workflow API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from enums import NodeType
from utils.webhooks import build_webhook_path


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
    parent_index: int | None = Field(
        default=None,
        description=(
            "Index of the owning Loop node in `nodes`, or None for a "
            "top-level node — same by-position reference as an edge's "
            "source_index/target_index, since the owning node's real "
            "database ID doesn't exist yet at import time either"
        ),
        ge=0,
    )


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


class WorkflowTemplateResponse(BaseModel):
    """Catalog metadata for a global workflow template (list view — no graph)."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(default=..., description="Stable template identifier")
    name: str = Field(default=..., description="Display name")
    description: str = Field(default=..., description="What this template does")


class WorkflowTemplateInstantiateRequest(BaseModel):
    """Payload for creating a workflow from a template."""

    name: str | None = Field(
        default=None,
        description="Name for the new workflow; defaults to the template's name",
        min_length=1,
        max_length=200,
    )


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

    @computed_field
    @property
    def webhook_path(self) -> str:
        """Return this workflow's stable signed public webhook path."""
        return build_webhook_path(self.id)
