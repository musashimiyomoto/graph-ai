"""Node catalog registry and validation helpers."""

from typing import Any

from enums import NodeType, ValidatorType
from exceptions import NodeDataValidationError
from node_catalog.schemas import (
    NodeCatalogItem,
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)

NODE_CATALOG: dict[NodeType, NodeCatalogItem] = {
    NodeType.INPUT: NodeCatalogItem(
        type=NodeType.INPUT,
        label="Input",
        icon_key="input",
        graph=NodeGraphSpec(has_input=False, has_output=True),
        defaults={"label": "Input node", "format": "txt"},
        fields=(
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="Input label",
                ),
                default="Input node",
            ),
            NodeFieldSpec(
                name="format",
                required=True,
                validators={ValidatorType.SELECT: ["txt"]},
                ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
                default="txt",
            ),
        ),
    ),
    NodeType.LLM: NodeCatalogItem(
        type=NodeType.LLM,
        label="LLM",
        icon_key="llm",
        graph=NodeGraphSpec(has_input=True, has_output=True),
        defaults={
            "label": "LLM node",
            "llm_provider_id": 0,
            "model": "",
            "system_prompt": "",
            "temperature": 0.7,
        },
        fields=(
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="LLM label",
                ),
                default="LLM node",
            ),
            NodeFieldSpec(
                name="llm_provider_id",
                required=True,
                validators={ValidatorType.GE: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.PROVIDER,
                    label="Provider",
                ),
                datasource=NodeFieldDataSource(
                    kind=NodeFieldDataSourceKind.LLM_PROVIDER,
                ),
            ),
            NodeFieldSpec(
                name="model",
                required=True,
                validators={ValidatorType.MIN_LENGTH: 1},
                ui=NodeFieldUI(widget=NodeFieldWidget.MODEL, label="Model"),
                datasource=NodeFieldDataSource(
                    kind=NodeFieldDataSourceKind.LLM_MODEL,
                    depends_on="llm_provider_id",
                ),
                default="",
            ),
            NodeFieldSpec(
                name="system_prompt",
                required=True,
                validators={},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXTAREA,
                    label="System prompt",
                    placeholder="You are a helpful assistant.",
                ),
                default="",
            ),
            NodeFieldSpec(
                name="temperature",
                required=True,
                validators={ValidatorType.GE: 0.0, ValidatorType.LE: 2.0},
                ui=NodeFieldUI(widget=NodeFieldWidget.NUMBER, label="Temperature"),
                default=0.7,
            ),
        ),
    ),
    NodeType.OUTPUT: NodeCatalogItem(
        type=NodeType.OUTPUT,
        label="Output",
        icon_key="output",
        graph=NodeGraphSpec(has_input=True, has_output=False),
        defaults={"label": "Output node", "format": "txt"},
        fields=(
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="Output label",
                ),
                default="Output node",
            ),
            NodeFieldSpec(
                name="format",
                required=True,
                validators={ValidatorType.SELECT: ["txt"]},
                ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
                default="txt",
            ),
        ),
    ),
}


def get_node_catalog() -> tuple[NodeCatalogItem, ...]:
    """Return full catalog for all supported node types.

    Returns:
        Ordered node catalog entries.

    """
    return tuple(NODE_CATALOG[node_type] for node_type in NodeType)


def get_node_spec(node_type: NodeType) -> NodeCatalogItem:
    """Return catalog entry for a specific node type.

    Args:
        node_type: Node type to resolve.

    Returns:
        Catalog item for the type.

    """
    return NODE_CATALOG[node_type]


def validate_node_data(node_type: NodeType, data: dict[str, Any]) -> dict[str, Any]:
    """Validate node payload against catalog specification.

    Args:
        node_type: Node type that owns the payload.
        data: Incoming node data.

    Returns:
        Validated data dictionary.

    Raises:
        NodeDataValidationError: If validation fails.

    """
    spec = get_node_spec(node_type=node_type)
    errors: list[str] = []
    fields_by_name = {field.name: field for field in spec.fields}

    unexpected = set(data.keys()) - set(fields_by_name.keys())
    if unexpected:
        errors.append(f"Unexpected fields: {', '.join(sorted(unexpected))}")

    for field in spec.fields:
        if field.required and field.name not in data:
            errors.append(f"Missing required field: '{field.name}'")
            continue

        if field.name not in data:
            continue

        _validate_field(field=field, value=data[field.name], errors=errors)

    if errors:
        raise NodeDataValidationError(message="; ".join(errors))

    return data


def _validate_field(*, field: NodeFieldSpec, value: object, errors: list[str]) -> None:
    """Validate one node field value.

    Args:
        field: Field schema definition.
        value: Value to validate.
        errors: Collector for validation errors.

    """
    validators = field.validators

    if ValidatorType.MIN_LENGTH in validators and (
        not isinstance(value, str)
        or len(value) < int(validators[ValidatorType.MIN_LENGTH])
    ):
        errors.append(
            f"Field '{field.name}' must be a string with "
            f"min length {validators[ValidatorType.MIN_LENGTH]}"
        )

    if ValidatorType.SELECT in validators:
        allowed = validators[ValidatorType.SELECT]
        if value not in allowed:
            options = ", ".join(str(option) for option in allowed)
            errors.append(f"Field '{field.name}' must be one of: {options}")

    if ValidatorType.GE in validators:
        threshold = float(validators[ValidatorType.GE])
        if not isinstance(value, int | float) or value < threshold:
            errors.append(f"Field '{field.name}' must be >= {threshold}")

    if ValidatorType.LE in validators:
        threshold = float(validators[ValidatorType.LE])
        if not isinstance(value, int | float) or value > threshold:
            errors.append(f"Field '{field.name}' must be <= {threshold}")
