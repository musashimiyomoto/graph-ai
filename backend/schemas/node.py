"""Schemas for node-related API payloads."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from enums import NodeType, PortType


class NodeFieldWidget(StrEnum):
    """UI widgets supported by node field rendering."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    OPTIONAL_NUMBER = "optional_number"
    SELECT = "select"
    PROVIDER = "provider"
    MODEL = "model"
    TELEGRAM_BOT = "telegram_bot"
    VECTOR_COLLECTION = "vector_collection"


class NodeFieldDataSourceKind(StrEnum):
    """Dynamic data source kinds for node fields."""

    LLM_PROVIDER = "llm_provider"
    LLM_MODEL = "llm_model"
    TELEGRAM_BOT = "telegram_bot"
    VECTOR_COLLECTION = "vector_collection"


class NodeFieldUI(BaseModel):
    """UI metadata for a node field."""

    model_config = ConfigDict(frozen=True)

    widget: NodeFieldWidget = Field(default=..., description="Widget kind")
    label: str = Field(default=..., description="Display label")
    placeholder: str | None = Field(default=None, description="Input placeholder")
    help: str | None = Field(default=None, description="Help text")
    step: float | None = Field(
        default=None,
        description="Numeric stepper increment; use 1 for integer fields "
        "(the UI defaults to 0.1 when unset)",
    )


class NodeFieldDataSource(BaseModel):
    """Dynamic source definition for a node field."""

    model_config = ConfigDict(frozen=True)

    kind: NodeFieldDataSourceKind = Field(default=..., description="Datasource kind")
    depends_on: str | None = Field(default=None, description="Dependency field name")


class NodeFieldVisibility(BaseModel):
    """Conditional visibility rule for a node field.

    The field is shown (and should only be persisted) when the named sibling
    field's current value equals ``equals``, or when ``not_equals`` is set,
    when it does *not* equal ``not_equals``. Exactly one of the two must be
    set. This keeps gated fields (e.g. a Telegram bot picker that only makes
    sense for ``format=telegram``, or a condition value hidden for a
    value-less condition type) declarative in the catalog instead of
    hardcoded per widget in the frontend.
    """

    model_config = ConfigDict(frozen=True)

    field: str = Field(default=..., description="Name of the controlling field")
    equals: Any = Field(default=None, description="Value that makes this field visible")
    not_equals: Any = Field(
        default=None, description="Value that makes this field hidden"
    )

    @model_validator(mode="after")
    def _check_exactly_one_condition(self) -> "NodeFieldVisibility":
        """Ensure exactly one of equals/not_equals is configured."""
        if (self.equals is None) == (self.not_equals is None):
            message = "NodeFieldVisibility requires exactly one of equals/not_equals"
            raise ValueError(message)
        return self


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
    visible_when: NodeFieldVisibility | None = Field(
        default=None,
        description="Show this field only when the rule is satisfied",
    )


class NodeGraphSpec(BaseModel):
    """Graph-connection metadata for a node type."""

    model_config = ConfigDict(frozen=True)

    has_input: bool = Field(default=..., description="Whether input handle exists")
    has_output: bool = Field(default=..., description="Whether output handle exists")
    input_port: PortType | None = Field(
        default=None, description="Input port data type (None when no input handle)"
    )
    output_port: PortType | None = Field(
        default=None, description="Output port data type (None when no output handle)"
    )
    output_handles: tuple[str, ...] | None = Field(
        default=None,
        description=(
            "Named output branches (e.g. condition true/false). None means a "
            "single implicit default handle."
        ),
    )


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
    parent_node_id: int | None = Field(
        default=None,
        description="Owning Loop node's ID, or None for a top-level graph node",
        gt=0,
    )


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
    parent_node_id: int | None = Field(
        default=None,
        description="Owning Loop node's ID, or None for a top-level graph node",
    )


class NodeCatalogDataSourceResponse(BaseModel):
    """Dynamic datasource metadata for a catalog field."""

    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(default=..., description="Datasource kind")
    depends_on: str | None = Field(default=None, description="Dependency field name")


class NodeCatalogVisibilityResponse(BaseModel):
    """Conditional visibility metadata for a catalog field."""

    model_config = ConfigDict(from_attributes=True)

    field: str = Field(default=..., description="Name of the controlling field")
    equals: Any = Field(default=None, description="Value that makes this field visible")
    not_equals: Any = Field(
        default=None, description="Value that makes this field hidden"
    )


class NodeCatalogFieldUIResponse(BaseModel):
    """UI metadata for a catalog field."""

    model_config = ConfigDict(from_attributes=True)

    widget: str = Field(default=..., description="Widget identifier")
    label: str = Field(default=..., description="UI label")
    placeholder: str | None = Field(default=None, description="Input placeholder")
    help: str | None = Field(default=None, description="Field help text")
    step: float | None = Field(default=None, description="Numeric stepper increment")


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
    visible_when: NodeCatalogVisibilityResponse | None = Field(
        default=None,
        description="Conditional visibility rule",
    )


class NodeCatalogGraphResponse(BaseModel):
    """Graph metadata for a node type."""

    model_config = ConfigDict(from_attributes=True)

    has_input: bool = Field(default=..., description="Node has input handle")
    has_output: bool = Field(default=..., description="Node has output handle")
    input_port: PortType | None = Field(default=None, description="Input port type")
    output_port: PortType | None = Field(default=None, description="Output port type")
    output_handles: list[str] | None = Field(
        default=None, description="Named output branches, if any"
    )


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
