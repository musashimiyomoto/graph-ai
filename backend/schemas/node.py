"""Schemas for node-related API payloads."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import NodeType


class NodeFieldWidget(StrEnum):
    """UI widgets supported by node field rendering."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    PROVIDER = "provider"
    MODEL = "model"


class NodeFieldDataSourceKind(StrEnum):
    """Dynamic data source kinds for node fields."""

    LLM_PROVIDER = "llm_provider"
    LLM_MODEL = "llm_model"


class NodeFieldUI(BaseModel):
    """UI metadata for a node field."""

    model_config = ConfigDict(frozen=True)

    widget: NodeFieldWidget = Field(default=..., description="Widget kind")
    label: str = Field(default=..., description="Display label")
    placeholder: str | None = Field(default=None, description="Input placeholder")
    help: str | None = Field(default=None, description="Help text")


class NodeFieldDataSource(BaseModel):
    """Dynamic source definition for a node field."""

    model_config = ConfigDict(frozen=True)

    kind: NodeFieldDataSourceKind = Field(default=..., description="Datasource kind")
    depends_on: str | None = Field(default=None, description="Dependency field name")


class NodeFieldSpec(BaseModel):
    """Schema definition for a single node data field."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(default=..., description="Field name")
    required: bool = Field(default=..., description="Required flag")
    validators: dict[str, Any] = Field(
        default_factory=dict,
        description="Validation rules by validator key",
    )
    ui: NodeFieldUI = Field(default=..., description="UI metadata")
    default: Any | None = Field(default=None, description="Default value")
    datasource: NodeFieldDataSource | None = Field(
        default=None,
        description="Dynamic datasource definition",
    )


class NodeGraphSpec(BaseModel):
    """Graph-connection metadata for a node type."""

    model_config = ConfigDict(frozen=True)

    has_input: bool = Field(default=..., description="Whether input handle exists")
    has_output: bool = Field(default=..., description="Whether output handle exists")


class NodeCatalogItem(BaseModel):
    """Full metadata entry for a node type."""

    model_config = ConfigDict(frozen=True)

    type: NodeType = Field(default=..., description="Node type")
    label: str = Field(default=..., description="Display label")
    icon_key: str = Field(default=..., description="Icon key")
    graph: NodeGraphSpec = Field(default=..., description="Graph metadata")
    fields: tuple[NodeFieldSpec, ...] = Field(
        default_factory=tuple,
        description="Field definitions",
    )


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
    fields: list[NodeCatalogFieldResponse] = Field(
        default_factory=list,
        description="Node field schema",
    )
