"""Loop input node handler.

The entry point of a Loop node's body. Unlike the top-level Input node, it
carries no `format` concept (Telegram/schedule are meaningless inside a loop
iteration) — it exists purely as the scoped graph's required single input,
same role as Input plays for the top-level graph.
"""

from enums import NodeType, PortType, ValidatorType
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from schemas import NodeFieldSpec, NodeFieldUI, NodeFieldWidget


class LoopInputNodeHandler:
    """Handler for loop input nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Return the current iteration's input value."""
        return NodeExecutionResult(output=context.input_value)


def _build_handler(deps: NodeHandlerDeps) -> LoopInputNodeHandler:
    """Build a loop input node handler."""
    del deps
    return LoopInputNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.LOOP_INPUT,
    label="Loop Input",
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
                placeholder="Loop Input label",
            ),
            default="Loop Input",
        ),
    ),
    build_handler=_build_handler,
)
