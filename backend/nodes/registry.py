"""Node handler registry for execution."""

from db.repositories import LLMProviderRepository
from enums import NodeType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeHandler
from nodes.input import InputNodeHandler
from nodes.llm import LLMNodeHandler
from nodes.output import OutputNodeHandler
from nodes.web_search import WebSearchNodeHandler


class NodeHandlerRegistry:
    """Registry that dispatches execution to node handlers."""

    def __init__(self, llm_provider_repository: LLMProviderRepository) -> None:
        """Initialize node handler mapping.

        Args:
            llm_provider_repository: Repository for LLM provider lookups.

        """
        self._handlers: dict[NodeType, NodeHandler] = {
            NodeType.INPUT: InputNodeHandler(),
            NodeType.LLM: LLMNodeHandler(
                llm_provider_repository=llm_provider_repository
            ),
            NodeType.WEB_SEARCH: WebSearchNodeHandler(),
            NodeType.OUTPUT: OutputNodeHandler(),
        }

    async def execute(
        self,
        *,
        node_type: NodeType,
        context: NodeExecutionContext,
    ) -> str:
        """Dispatch node execution to a registered handler.

        Args:
            node_type: Type of node to execute.
            context: Node execution context.

        Returns:
            Node execution output.

        Raises:
            ExecutionGraphValidationError: If node type is unsupported.

        """
        handler = self._handlers.get(node_type)
        if handler is None:
            message = f"Unsupported node type: {node_type}"
            raise ExecutionGraphValidationError(message=message)

        return await handler.execute(context)
