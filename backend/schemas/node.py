"""Schemas for node-related API payloads."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import NodeType


class NodeCreate(BaseModel):
    """Payload for creating a node."""

    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    type: NodeType = Field(default=..., description="Node type")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Node configuration data"
    )
    position_x: float = Field(default=0.0, description="X position on canvas")
    position_y: float = Field(default=0.0, description="Y position on canvas")


class NodeUpdate(BaseModel):
    """Payload for updating a node."""

    data: dict[str, Any] | None = Field(
        default=None, description="Node configuration data"
    )
    position_x: float | None = Field(default=None, description="X position on canvas")
    position_y: float | None = Field(default=None, description="Y position on canvas")


class NodeResponse(BaseModel):
    """Response model for nodes."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Node ID", gt=0)
    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    type: NodeType = Field(default=..., description="Node type")
    data: dict[str, Any] = Field(default=..., description="Node configuration data")
    position_x: float = Field(default=..., description="X position on canvas")
    position_y: float = Field(default=..., description="Y position on canvas")
