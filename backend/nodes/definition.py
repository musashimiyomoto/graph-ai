"""Node definition: co-locates identity, metadata, ports, and handler factory."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from db.repositories import (
    LLMProviderRepository,
    MCPServerRepository,
    PostgresConnectionRepository,
)
from enums import NodeType, PortCoercion, PortType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeHandler
from nodes.value import JSONValue, NodeValue
from schemas import NodeFieldSpec, NodeGraphSpec

PORT_COERCIONS: dict[PortCoercion, tuple[PortType, PortType]] = {
    PortCoercion.TEXT_TO_JSON: (PortType.TEXT, PortType.JSON),
    PortCoercion.JSON_TO_TEXT: (PortType.JSON, PortType.TEXT),
    PortCoercion.TEXT_TO_LIST: (PortType.TEXT, PortType.LIST),
    PortCoercion.LIST_TO_TEXT: (PortType.LIST, PortType.TEXT),
    PortCoercion.JSON_TO_LIST: (PortType.JSON, PortType.LIST),
    PortCoercion.LIST_TO_JSON: (PortType.LIST, PortType.JSON),
    PortCoercion.IMAGE_TO_FILE: (PortType.IMAGE, PortType.FILE),
    PortCoercion.AUDIO_TO_FILE: (PortType.AUDIO, PortType.FILE),
    PortCoercion.VIDEO_TO_FILE: (PortType.VIDEO, PortType.FILE),
}


@dataclass(frozen=True)
class NodeHandlerDeps:
    """Dependencies available to node handler factories."""

    llm_provider_repository: LLMProviderRepository
    postgres_connection_repository: PostgresConnectionRepository
    mcp_server_repository: MCPServerRepository


@dataclass(frozen=True)
class NodeDefinition:
    """Full definition of a node type in a single place.

    Registering a node means declaring one of these next to its handler and adding
    it to ``NODE_DEFINITIONS`` in ``nodes/registry.py``.
    """

    type: NodeType
    label: str
    icon_key: str
    graph: NodeGraphSpec
    fields: tuple[NodeFieldSpec, ...]
    build_handler: Callable[[NodeHandlerDeps], NodeHandler]


def ports_compatible(
    output_port: PortType,
    input_port: PortType,
    coercion: PortCoercion | None = None,
) -> bool:
    """Return whether a source output port can feed a target input port.

    Exact types connect without conversion. Different types connect only when
    the edge explicitly stores the one declared conversion for that pair.

    Args:
        output_port: The source node's output port type.
        input_port: The target node's input port type.
        coercion: Explicit conversion stored on the edge, if any.

    Returns:
        Whether the connection and conversion declaration are compatible.

    """
    if output_port is input_port:
        return coercion is None
    if coercion is None:
        return False
    return PORT_COERCIONS.get(coercion) == (output_port, input_port)


def required_port_coercion(
    output_port: PortType, input_port: PortType
) -> PortCoercion | None:
    """Return the declared conversion for a mismatched pair, if supported."""
    if output_port is input_port:
        return None
    return next(
        (
            coercion
            for coercion, pair in PORT_COERCIONS.items()
            if pair == (output_port, input_port)
        ),
        None,
    )


def resolve_graph_port(
    graph: NodeGraphSpec,
    node_data: dict[str, object],
    *,
    output: bool,
) -> PortType | None:
    """Resolve a fixed or node-configured port type from graph metadata."""
    default = graph.output_port if output else graph.input_port
    field = graph.output_port_field if output else graph.input_port_field
    options = graph.output_port_options if output else graph.input_port_options
    if default is None or field is None:
        return default
    raw_type = node_data.get(field, default.value)
    try:
        resolved = PortType(raw_type)
    except ValueError as exc:
        direction = "output" if output else "input"
        message = f"Node has an unsupported configured {direction} port type"
        raise ValueError(message) from exc
    if resolved not in options:
        direction = "output" if output else "input"
        message = f"Node has a disallowed configured {direction} port type"
        raise ValueError(message)
    return resolved


def _text_to_json(value: NodeValue) -> NodeValue:
    """Parse text as a structured JSON value."""
    try:
        parsed = json.loads(value.require_text())
    except json.JSONDecodeError as exc:
        raise ExecutionGraphValidationError(
            message="Edge coercion 'text_to_json' received invalid JSON"
        ) from exc
    return NodeValue.json(cast("JSONValue", parsed))


def _text_to_list(value: NodeValue) -> NodeValue:
    """Parse text as a JSON array value."""
    try:
        parsed = json.loads(value.require_text())
    except json.JSONDecodeError as exc:
        raise ExecutionGraphValidationError(
            message="Edge coercion 'text_to_list' received invalid JSON"
        ) from exc
    if not isinstance(parsed, list):
        raise ExecutionGraphValidationError(
            message="Edge coercion 'text_to_list' requires a JSON array"
        )
    return NodeValue.list(cast("list[JSONValue]", parsed))


def _structured_to_text(value: NodeValue) -> NodeValue:
    """Serialize a JSON or list value without losing its structure."""
    return NodeValue.text(json.dumps(value.value, ensure_ascii=False))


def _json_to_list(value: NodeValue) -> NodeValue:
    """Narrow a JSON value to a list after checking its runtime shape."""
    if not isinstance(value.value, list):
        raise ExecutionGraphValidationError(
            message="Edge coercion 'json_to_list' requires a JSON array"
        )
    return NodeValue.list(value.value)


def _list_to_json(value: NodeValue) -> NodeValue:
    """Widen a list value to JSON without serializing it."""
    return NodeValue.json(value.value)


def _artifact_to_file(value: NodeValue) -> NodeValue:
    """Widen a media artifact to the generic file kind."""
    if value.artifact is None:
        raise ExecutionGraphValidationError(
            message="Media-to-file coercion requires an artifact"
        )
    return NodeValue.artifact_value(
        PortType.FILE,
        value.artifact,
        metadata=value.metadata,
    )


_VALUE_COERCERS: dict[PortCoercion, Callable[[NodeValue], NodeValue]] = {
    PortCoercion.TEXT_TO_JSON: _text_to_json,
    PortCoercion.JSON_TO_TEXT: _structured_to_text,
    PortCoercion.TEXT_TO_LIST: _text_to_list,
    PortCoercion.LIST_TO_TEXT: _structured_to_text,
    PortCoercion.JSON_TO_LIST: _json_to_list,
    PortCoercion.LIST_TO_JSON: _list_to_json,
    PortCoercion.IMAGE_TO_FILE: _artifact_to_file,
    PortCoercion.AUDIO_TO_FILE: _artifact_to_file,
    PortCoercion.VIDEO_TO_FILE: _artifact_to_file,
}


def coerce_node_value(value: NodeValue, coercion: PortCoercion | None) -> NodeValue:
    """Apply one explicit edge conversion while preserving structured data."""
    if coercion is None:
        return value
    source_type, _ = PORT_COERCIONS[coercion]
    if value.kind is not source_type:
        raise ExecutionGraphValidationError(
            message=(
                f"Edge coercion '{coercion.value}' expected {source_type.value}, "
                f"received {value.kind.value}"
            )
        )
    return _VALUE_COERCERS[coercion](value)
