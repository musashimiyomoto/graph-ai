"""Input node handler."""

from channels.registry import build_channel_fields
from enums import NodeType, PortType, ValidatorType
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
)


class InputNodeHandler:
    """Handler for input nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Return execution input value."""
        return NodeExecutionResult(output=context.input_value)


def _build_handler(deps: NodeHandlerDeps) -> InputNodeHandler:
    """Build an input node handler."""
    del deps
    return InputNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.INPUT,
    label="Input",
    icon_key="input",
    graph=graph_spec(
        output_type=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Input label",
            ),
            default="Input node",
        ),
        *build_channel_fields(output=False),
    ),
    build_handler=_build_handler,
)
