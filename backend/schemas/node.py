"""Schemas for node-related API payloads."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import NodeType


class NodeCreate(BaseModel):
    """Payload for creating a node."""

    workflow_id: int = Field(default=..., description="Workflow ID", gt=0)
    type: NodeType = Field(default=..., description="Node type")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Node configuration data",
    )
    position_x: float = Field(default=0.0, description="X position on canvas")
    position_y: float = Field(default=0.0, description="Y position on canvas")


class NodeUpdate(BaseModel):
    """Payload for updating a node."""

    data: dict[str, Any] | None = Field(
        default=None,
        description="Node configuration data",
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


class NodeCatalogDataSourceResponse(BaseModel):
    """Dynamic datasource metadata for a catalog field."""

    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(default=..., description="Datasource kind")
    depends_on: str | None = Field(default=None, description="Dependency field name")


class NodeCatalogFieldUIResponse(BaseModel):
    """UI metadata for a catalog field."""

    model_config = ConfigDict(from_attributes=True)

    widget: str = Field(default=..., description="Widget identifier")
    label: str = Field(default=..., description="UI label")
    placeholder: str | None = Field(default=None, description="Input placeholder")
    help: str | None = Field(default=None, description="Field help text")


class NodeCatalogFieldResponse(BaseModel):
    """Field metadata entry for node catalog."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(default=..., description="Field name")
    required: bool = Field(default=..., description="Whether field is required")
    validators: dict[str, Any] = Field(default_factory=dict, description="Validators")
    ui: NodeCatalogFieldUIResponse = Field(default=..., description="UI metadata")
    default: Any | None = Field(default=None, description="Default value")
    datasource: NodeCatalogDataSourceResponse | None = Field(
        default=None,
        description="Dynamic datasource metadata",
    )


class NodeCatalogGraphResponse(BaseModel):
    """Graph metadata for a node type."""

    model_config = ConfigDict(from_attributes=True)

    has_input: bool = Field(default=..., description="Node has input handle")
    has_output: bool = Field(default=..., description="Node has output handle")


class NodeCatalogItemResponse(BaseModel):
    """Catalog entry for a node type."""

    model_config = ConfigDict(from_attributes=True)

    type: NodeType = Field(default=..., description="Node type")
    label: str = Field(default=..., description="Human-readable label")
    icon_key: str = Field(default=..., description="Icon key for frontend")
    graph: NodeCatalogGraphResponse = Field(default=..., description="Graph metadata")
    defaults: dict[str, Any] = Field(default_factory=dict, description="Default data")
    fields: list[NodeCatalogFieldResponse] = Field(
        default_factory=list,
        description="Node field schema",
    )
