"""Loop output node handler.

The exit point of a Loop node's body. Unlike the top-level Output node, it
carries no `format`/delivery concept — the recursive loop runner reads its
result directly (as the collected list element in list mode, or as the next
iteration's Loop Input value in condition mode), it never delivers anywhere
on its own.
"""

from enums import NodeType, PortType, ValidatorType
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import NodeFieldSpec, NodeFieldUI, NodeFieldWidget, NodeGraphSpec


class LoopOutputNodeHandler:
    """Handler for loop output nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Join upstream values into this iteration's result."""
        return NodeExecutionResult(output="\n".join(context.parent_values))


def _build_handler(deps: NodeHandlerDeps) -> LoopOutputNodeHandler:
    """Build a loop output node handler."""
    del deps
    return LoopOutputNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.LOOP_OUTPUT,
    label="Loop Output",
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
                placeholder="Loop Output label",
            ),
            default="Loop Output",
        ),
    ),
    build_handler=_build_handler,
)
