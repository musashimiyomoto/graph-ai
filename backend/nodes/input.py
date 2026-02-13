"""Input node handler."""

from nodes.base import NodeExecutionContext


class InputNodeHandler:
    """Handler for input nodes."""

    async def execute(self, context: NodeExecutionContext) -> str:
        """Return execution input value."""
        return context.input_value
