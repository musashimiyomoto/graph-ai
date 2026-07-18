"""Call Workflow node definition.

The execution usecase owns the recursive graph runner for this node. The
handler exists only so the registry remains complete for every NodeType.
"""

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)


class CallWorkflowNodeHandler:
    """Placeholder handler; execution is special-cased by the graph runner."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Reject direct dispatch because recursive execution needs graph context."""
        del context
        raise ExecutionGraphValidationError(
            message="Call Workflow node must be executed by the graph runner"
        )


def _build_handler(deps: NodeHandlerDeps) -> CallWorkflowNodeHandler:
    """Build the registry placeholder handler."""
    del deps
    return CallWorkflowNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.CALL_WORKFLOW,
    label="Call Workflow",
    icon_key="call_workflow",
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
            default="Call Workflow node",
        ),
        NodeFieldSpec(
            name="target_workflow_id",
            required=True,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(widget=NodeFieldWidget.WORKFLOW, label="Workflow"),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.WORKFLOW),
        ),
    ),
    build_handler=_build_handler,
)
