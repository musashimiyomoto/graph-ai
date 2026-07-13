"""Loop node catalog definition.

Unlike every other node type, Loop has no real ``NodeHandler`` — it can't be
a plain stateless handler like the rest, since running its body means
recursively calling back into the graph runner itself (build a scoped
sub-graph, drive node-by-node execution over it once per iteration, record
each inner node's own ``node_executions`` rows). That's something a
``NodeHandler`` has no way to do: handlers only see a single
``NodeExecutionContext``, not the execution usecase that owns the recursive
runner.

So execution is special-cased directly in
``ExecutionUsecase._run_node_once``, which intercepts ``NodeType.LOOP``
before ever reaching ``NodeHandlerRegistry.execute`` — see
``ExecutionUsecase._run_loop_node``. This module still declares a
``NodeDefinition`` (for the catalog: field schema, port types, node
palette) and a handler (for registry completeness / the
``NodeHandlerRegistry`` invariant that every ``NodeType`` has one), but that
handler's ``execute`` is unreachable in a real run and only raises to make
that explicit if the special-case branch is ever accidentally bypassed.
"""

from enums import ConditionType, LoopMode, NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
    NodeGraphSpec,
)


class LoopNodeHandler:
    """Placeholder handler for loop nodes.

    Never actually invoked — ``ExecutionUsecase._run_node_once`` intercepts
    ``NodeType.LOOP`` before dispatching to the node registry. Exists only so
    every ``NodeType`` has exactly one registered handler.
    """

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Raise: Loop execution must go through `ExecutionUsecase._run_loop_node`."""
        del context
        message = (
            "Loop nodes are executed by ExecutionUsecase._run_loop_node, "
            "never dispatched through the node registry"
        )
        raise ExecutionGraphValidationError(message=message)


def _build_handler(deps: NodeHandlerDeps) -> LoopNodeHandler:
    """Build a loop node handler."""
    del deps
    return LoopNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.LOOP,
    label="Loop",
    icon_key="loop",
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
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Loop label",
            ),
            default="Loop node",
        ),
        NodeFieldSpec(
            name="mode",
            required=True,
            validators={
                ValidatorType.SELECT.value: [member.value for member in LoopMode]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Mode",
                help=(
                    "List: run the body once per element of an upstream JSON "
                    "array, collecting results back into a JSON array. "
                    "Condition: re-run the body, feeding each iteration's "
                    "result into the next, until the stop condition matches."
                ),
            ),
            default=LoopMode.LIST.value,
        ),
        NodeFieldSpec(
            name="condition_type",
            required=False,
            validators={
                ValidatorType.SELECT.value: [member.value for member in ConditionType]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Stop condition",
                help="How to evaluate each iteration's result to decide when to stop.",
            ),
            default=ConditionType.CONTAINS.value,
            visible_when=NodeFieldVisibility(
                field="mode", equals=LoopMode.CONDITION.value
            ),
        ),
        NodeFieldSpec(
            name="value",
            required=False,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Value",
                placeholder="Text or pattern to compare against",
            ),
            default="",
            visible_when=NodeFieldVisibility(
                field="mode", equals=LoopMode.CONDITION.value
            ),
        ),
        NodeFieldSpec(
            name="case_sensitive",
            required=False,
            validators={ValidatorType.SELECT.value: ["true", "false"]},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Case sensitive",
            ),
            default="false",
            visible_when=NodeFieldVisibility(
                field="mode", equals=LoopMode.CONDITION.value
            ),
        ),
    ),
    build_handler=_build_handler,
)
