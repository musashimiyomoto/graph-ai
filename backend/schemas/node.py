"""Schemas for node-related API payloads."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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
    EMAIL_ACCOUNT = "email_account"
    VECTOR_COLLECTION = "vector_collection"
    POSTGRES_CONNECTION = "postgres_connection"
    WORKFLOW = "workflow"
    SWITCH_BRANCHES = "switch_branches"
    MCP_SERVER = "mcp_server"
    MCP_TOOL = "mcp_tool"


class NodeFieldDataSourceKind(StrEnum):
    """Dynamic data source kinds for node fields."""

    LLM_PROVIDER = "llm_provider"
    LLM_MODEL = "llm_model"
    TELEGRAM_BOT = "telegram_bot"
    EMAIL_ACCOUNT = "email_account"
    VECTOR_COLLECTION = "vector_collection"
    POSTGRES_CONNECTION = "postgres_connection"
    WORKFLOW = "workflow"
    MCP_SERVER = "mcp_server"
    MCP_TOOL = "mcp_tool"


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


class NodePortSpec(BaseModel):
    """One named typed data port exposed by a node definition."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(default=..., min_length=1, description="Stable port name")
    label: str = Field(default=..., min_length=1, description="UI port label")
    type: PortType = Field(default=..., description="Default port value type")
    required: bool = Field(
        default=True,
        description="Whether graph validation requires this input to be connected",
    )
    type_field: str | None = Field(
        default=None,
        description="Node-data field selecting the effective type, when configurable",
    )
    allowed_types: tuple[PortType, ...] = Field(
        default_factory=tuple,
        description="Types selectable through type_field; empty for a fixed port",
    )

    @model_validator(mode="after")
    def _validate_dynamic_type(self) -> "NodePortSpec":
        """Keep configurable-port metadata internally consistent."""
        if bool(self.type_field) != bool(self.allowed_types):
            message = "Configurable ports require a type_field and allowed_types"
            raise ValueError(message)
        if self.allowed_types and self.type not in self.allowed_types:
            message = "Default port type must be one of allowed_types"
            raise ValueError(message)
        return self


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
    input_name: str = Field(default="input", description="Stable input port name")
    output_name: str = Field(default="output", description="Stable output port name")
    input_label: str = Field(default="Input", description="Input port UI label")
    output_label: str = Field(default="Output", description="Output port UI label")
    input_port_field: str | None = Field(
        default=None,
        description="Node-data field selecting the effective input type",
    )
    output_port_field: str | None = Field(
        default=None,
        description="Node-data field selecting the effective output type",
    )
    input_port_options: tuple[PortType, ...] = Field(
        default_factory=tuple,
        description="Allowed configurable input types",
    )
    output_port_options: tuple[PortType, ...] = Field(
        default_factory=tuple,
        description="Allowed configurable output types",
    )
    additional_inputs: tuple[NodePortSpec, ...] = Field(
        default_factory=tuple,
        description="Additional independently addressable ordinary input ports",
    )
    additional_outputs: tuple[NodePortSpec, ...] = Field(
        default_factory=tuple,
        description="Additional independently addressable ordinary output ports",
    )

    @model_validator(mode="after")
    def _validate_ports(self) -> "NodeGraphSpec":
        """Keep legacy booleans/types and configurable metadata consistent."""
        self._validate_primary_ports()
        self._validate_additional_ports()
        return self

    def _validate_primary_ports(self) -> None:
        """Validate legacy primary-port and dynamic-type metadata."""
        if self.has_input != (self.input_port is not None):
            message = "has_input must match whether input_port is configured"
            raise ValueError(message)
        if self.has_output != (self.output_port is not None):
            message = "has_output must match whether output_port is configured"
            raise ValueError(message)
        if bool(self.input_port_field) != bool(self.input_port_options):
            message = "Configurable input ports require a field and allowed types"
            raise ValueError(message)
        if bool(self.output_port_field) != bool(self.output_port_options):
            message = "Configurable output ports require a field and allowed types"
            raise ValueError(message)
        if (
            self.input_port is not None
            and self.input_port_options
            and self.input_port not in self.input_port_options
        ):
            message = "Default input_port must be one of input_port_options"
            raise ValueError(message)
        if (
            self.output_port is not None
            and self.output_port_options
            and self.output_port not in self.output_port_options
        ):
            message = "Default output_port must be one of output_port_options"
            raise ValueError(message)

    def _validate_additional_ports(self) -> None:
        """Validate independently addressable ordinary port declarations."""
        if self.additional_inputs and not self.has_input:
            message = "Additional inputs require a primary input port"
            raise ValueError(message)
        if self.additional_outputs and not self.has_output:
            message = "Additional outputs require a primary output port"
            raise ValueError(message)
        input_names = (self.input_name, *(port.name for port in self.additional_inputs))
        output_names = (
            self.output_name,
            *(port.name for port in self.additional_outputs),
        )
        if len(input_names) != len(set(input_names)):
            message = "Input port names must be unique"
            raise ValueError(message)
        if len(output_names) != len(set(output_names)):
            message = "Output port names must be unique"
            raise ValueError(message)
        if self.output_handles is not None and self.additional_outputs:
            message = "Routing handles cannot be combined with ordinary multi-outputs"
            raise ValueError(message)

    @computed_field
    @property
    def inputs(self) -> tuple[NodePortSpec, ...]:
        """Expose the current single input as a named typed-port collection."""
        if self.input_port is None:
            return ()
        return (
            NodePortSpec(
                name=self.input_name,
                label=self.input_label,
                type=self.input_port,
                type_field=self.input_port_field,
                allowed_types=self.input_port_options,
            ),
            *self.additional_inputs,
        )

    @computed_field
    @property
    def outputs(self) -> tuple[NodePortSpec, ...]:
        """Expose the current single output as a named typed-port collection."""
        if self.output_port is None:
            return ()
        return (
            NodePortSpec(
                name=self.output_name,
                label=self.output_label,
                type=self.output_port,
                type_field=self.output_port_field,
                allowed_types=self.output_port_options,
            ),
            *self.additional_outputs,
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
    inputs: list[NodePortSpec] = Field(
        default_factory=list, description="Named typed input ports"
    )
    outputs: list[NodePortSpec] = Field(
        default_factory=list, description="Named typed output ports"
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
