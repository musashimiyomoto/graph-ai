"""Node registry: the single registration point for node types.

Handlers and the UI catalog are both derived from ``NODE_DEFINITIONS`` — adding a
node type means declaring a ``NodeDefinition`` next to its handler and adding it to
this list (plus its ``NodeType`` enum member).
"""

from enums import NodeType
from exceptions import ExecutionGraphValidationError
from nodes.approval import DEFINITION as APPROVAL_DEFINITION
from nodes.base import NodeExecutionContext, NodeExecutionResult, NodeHandler
from nodes.call_workflow import DEFINITION as CALL_WORKFLOW_DEFINITION
from nodes.code_transform import DEFINITION as CODE_TRANSFORM_DEFINITION
from nodes.condition import DEFINITION as CONDITION_DEFINITION
from nodes.definition import NodeDefinition, NodeHandlerDeps, ports_compatible
from nodes.delay import DEFINITION as DELAY_DEFINITION
from nodes.http_request import DEFINITION as HTTP_REQUEST_DEFINITION
from nodes.input import DEFINITION as INPUT_DEFINITION
from nodes.llm import DEFINITION as LLM_DEFINITION
from nodes.loop import DEFINITION as LOOP_DEFINITION
from nodes.loop_input import DEFINITION as LOOP_INPUT_DEFINITION
from nodes.loop_output import DEFINITION as LOOP_OUTPUT_DEFINITION
from nodes.mcp_tool import DEFINITION as MCP_TOOL_DEFINITION
from nodes.output import DEFINITION as OUTPUT_DEFINITION
from nodes.switch import DEFINITION as SWITCH_DEFINITION
from nodes.switch import switch_output_handles
from nodes.table import DEFINITION as TABLE_DEFINITION
from nodes.template import DEFINITION as TEMPLATE_DEFINITION
from nodes.translate import DEFINITION as TRANSLATE_DEFINITION
from nodes.vector_ingest import DEFINITION as VECTOR_INGEST_DEFINITION
from nodes.vector_search import DEFINITION as VECTOR_SEARCH_DEFINITION
from nodes.web_search import DEFINITION as WEB_SEARCH_DEFINITION
from schemas import NodeCatalogItem

NODE_DEFINITIONS: tuple[NodeDefinition, ...] = (
    INPUT_DEFINITION,
    LLM_DEFINITION,
    TRANSLATE_DEFINITION,
    DELAY_DEFINITION,
    WEB_SEARCH_DEFINITION,
    TEMPLATE_DEFINITION,
    HTTP_REQUEST_DEFINITION,
    CONDITION_DEFINITION,
    SWITCH_DEFINITION,
    MCP_TOOL_DEFINITION,
    CODE_TRANSFORM_DEFINITION,
    CALL_WORKFLOW_DEFINITION,
    APPROVAL_DEFINITION,
    VECTOR_INGEST_DEFINITION,
    VECTOR_SEARCH_DEFINITION,
    TABLE_DEFINITION,
    LOOP_DEFINITION,
    LOOP_INPUT_DEFINITION,
    LOOP_OUTPUT_DEFINITION,
    OUTPUT_DEFINITION,
)

_DEFINITIONS_BY_TYPE: dict[NodeType, NodeDefinition] = {
    definition.type: definition for definition in NODE_DEFINITIONS
}


def get_node_definition(node_type: NodeType) -> NodeDefinition:
    """Return the definition for a node type.

    Args:
        node_type: Node type to look up.

    Returns:
        The registered node definition.

    Raises:
        ExecutionGraphValidationError: If the node type is unregistered.

    """
    definition = _DEFINITIONS_BY_TYPE.get(node_type)
    if definition is None:
        message = f"Unsupported node type: {node_type}"
        raise ExecutionGraphValidationError(message=message)
    return definition


def build_node_catalog() -> dict[NodeType, NodeCatalogItem]:
    """Build the node catalog (UI metadata) from the registered definitions."""
    return {
        definition.type: NodeCatalogItem(
            type=definition.type,
            label=definition.label,
            icon_key=definition.icon_key,
            graph=definition.graph,
            fields=definition.fields,
        )
        for definition in NODE_DEFINITIONS
    }


def get_node_output_handles(
    node_type: NodeType,
    node_data: dict[str, object],
) -> tuple[str, ...] | None:
    """Return static or node-configured output handles for one node."""
    if node_type is NodeType.SWITCH:
        return switch_output_handles(node_data)
    return get_node_definition(node_type).graph.output_handles


def check_source_handle(
    node_type: NodeType,
    node_data: dict[str, object],
    source_handle: str | None,
) -> str | None:
    """Return a validation error when an edge uses an invalid source handle."""
    output_handles = get_node_output_handles(node_type, node_data)
    if output_handles is None:
        if source_handle is None:
            return None
        return (
            f"Node type '{node_type.value}' has a single default output handle; "
            "source_handle must be omitted"
        )
    if source_handle in output_handles:
        return None
    options = ", ".join(output_handles)
    return (
        f"Node type '{node_type.value}' requires source_handle to be one of: {options}"
    )


def check_edge_ports(source_type: NodeType, target_type: NodeType) -> str | None:
    """Check whether a source output can feed a target input.

    Args:
        source_type: Type of the edge's source node.
        target_type: Type of the edge's target node.

    Returns:
        A human-readable reason when the connection is invalid, else None.

    """
    output_port = get_node_definition(source_type).graph.output_port
    input_port = get_node_definition(target_type).graph.input_port

    if output_port is None:
        return f"Node type '{source_type.value}' has no output port"
    if input_port is None:
        return f"Node type '{target_type.value}' has no input port"
    if not ports_compatible(output_port, input_port):
        return (
            f"Incompatible ports: '{source_type.value}' outputs "
            f"'{output_port.value}' but '{target_type.value}' expects "
            f"'{input_port.value}'"
        )
    return None


class NodeHandlerRegistry:
    """Registry that dispatches execution to node handlers."""

    def __init__(self, deps: NodeHandlerDeps) -> None:
        """Build the handler map from the registered definitions.

        Args:
            deps: Shared dependencies passed to each handler factory.

        """
        self._handlers: dict[NodeType, NodeHandler] = {
            definition.type: definition.build_handler(deps)
            for definition in NODE_DEFINITIONS
        }

    async def execute(
        self,
        *,
        node_type: NodeType,
        context: NodeExecutionContext,
    ) -> NodeExecutionResult:
        """Dispatch node execution to a registered handler.

        Args:
            node_type: Type of node to execute.
            context: Node execution context.

        Returns:
            Node execution result.

        Raises:
            ExecutionGraphValidationError: If node type is unsupported.

        """
        handler = self._handlers.get(node_type)
        if handler is None:
            message = f"Unsupported node type: {node_type}"
            raise ExecutionGraphValidationError(message=message)

        return await handler.execute(context)
