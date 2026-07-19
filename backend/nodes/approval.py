"""Approval node catalog definition.

Execution is special-cased by the graph runner because reaching this node
durably pauses the execution instead of returning an immediate result.
"""

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import NodeFieldSpec, NodeFieldUI, NodeFieldWidget, NodeGraphSpec


class ApprovalNodeHandler:
    """Placeholder handler; approval requires execution lifecycle access."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Reject direct dispatch because the graph runner owns pausing."""
        del context
        raise ExecutionGraphValidationError(
            message="Approval node must be executed by the graph runner"
        )


def _build_handler(deps: NodeHandlerDeps) -> ApprovalNodeHandler:
    """Build the registry placeholder handler."""
    del deps
    return ApprovalNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.APPROVAL,
    label="Approval",
    icon_key="approval",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(widget=NodeFieldWidget.TEXT, label="Label"),
            default="Approval node",
        ),
        NodeFieldSpec(
            name="prompt",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Approval request",
                placeholder="Review this value before the workflow continues",
            ),
            default="Approve the next step?",
        ),
    ),
    build_handler=_build_handler,
)
