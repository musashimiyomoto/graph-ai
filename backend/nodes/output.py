"""Output node handler."""

from nodes.base import NodeExecutionContext


class OutputNodeHandler:
    """Handler for output nodes."""

    async def execute(self, context: NodeExecutionContext) -> str:
        """Join upstream values into final output."""
        return "\n".join(context.parent_values)
