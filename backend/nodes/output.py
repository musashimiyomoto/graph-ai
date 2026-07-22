"""Output node handler."""

from channels.registry import build_channel_fields
from enums import NodeType, PortType, ValidatorType
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)


class OutputNodeHandler:
    """Handler for output nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Join upstream values into final output."""
        return NodeExecutionResult.text(context.joined_parent_text())


def _build_handler(deps: NodeHandlerDeps) -> OutputNodeHandler:
    """Build an output node handler."""
    del deps
    return OutputNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.OUTPUT,
    label="Output",
    icon_key="output",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=False,
        input_port=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Output label",
            ),
            default="Output node",
        ),
        *build_channel_fields(output=True),
    ),
    build_handler=_build_handler,
)
