"""Node definition: co-locates identity, metadata, ports, and handler factory."""

from collections.abc import Callable
from dataclasses import dataclass

from db.repositories import LLMProviderRepository, PostgresConnectionRepository
from enums import NodeType, PortType
from nodes.base import NodeHandler
from schemas import NodeFieldSpec, NodeGraphSpec


@dataclass(frozen=True)
class NodeHandlerDeps:
    """Dependencies available to node handler factories."""

    llm_provider_repository: LLMProviderRepository
    postgres_connection_repository: PostgresConnectionRepository


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


def ports_compatible(output_port: PortType, input_port: PortType) -> bool:
    """Return whether a source output port can feed a target input port.

    Exact-match today; this is the single choke point where a future coercion
    table (e.g. text -> json) can widen compatibility.

    Args:
        output_port: The source node's output port type.
        input_port: The target node's input port type.

    Returns:
        Whether the connection is type-compatible.

    """
    return output_port is input_port
