"""Condition/router node handler.

Evaluates a condition against the upstream text and routes it to one of two
output handles (``true``/``false``) unchanged, letting downstream branches
diverge. See ``nodes/definition.py`` for how ``NodeGraphSpec.output_handles``
and ``NodeExecutionResult.selected_handle`` combine to make this possible
without any per-node-type branching in the execution engine.
"""

import re

from enums import ConditionBranch, ConditionType, NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from nodes.rendering import upstream_text
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
    NodeGraphSpec,
)


def evaluate_condition(
    *,
    condition_type: ConditionType,
    text: str,
    case_sensitive: bool,
    value: str | None,
) -> bool:
    """Evaluate a condition against text, independent of any node context.

    Shared by the Condition/Router node and the Loop node's condition-mode
    stop check, so both use the exact same matching rules without either
    depending on ``NodeExecutionContext``.

    Args:
        condition_type: How to evaluate ``text``.
        text: The text being evaluated.
        case_sensitive: Whether comparisons are case-sensitive.
        value: The comparison value; required for every condition type except
            ``NOT_EMPTY``.

    Returns:
        Whether the condition matched.

    Raises:
        ExecutionGraphValidationError: If ``value`` is required but empty, or
            it's an invalid regular expression under ``REGEX``.

    """
    if condition_type is ConditionType.NOT_EMPTY:
        return bool(text.strip())

    if not value:
        message = "Condition requires a non-empty value"
        raise ExecutionGraphValidationError(message=message)

    if condition_type is ConditionType.CONTAINS:
        if case_sensitive:
            return value in text
        return value.casefold() in text.casefold()

    if condition_type is ConditionType.EQUALS:
        if case_sensitive:
            return text == value
        return text.casefold() == value.casefold()

    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(value, text, flags=flags) is not None
    except re.error as exc:
        message = "Condition has an invalid regular expression"
        raise ExecutionGraphValidationError(message=message) from exc


class ConditionNodeHandler:
    """Handler for condition/router nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Evaluate the configured condition and route the input onward.

        Args:
            context: Node execution context.

        Returns:
            The unchanged upstream text, routed to the ``true`` or ``false``
            output handle.

        Raises:
            ExecutionGraphValidationError: If the node configuration is invalid.

        """
        text = upstream_text(context)
        condition_type = self._read_condition_type(context)
        case_sensitive = self._read_case_sensitive(context)
        value = context.node_data.get("value")
        matched = evaluate_condition(
            condition_type=condition_type,
            text=text,
            case_sensitive=case_sensitive,
            value=value if isinstance(value, str) else None,
        )
        branch = ConditionBranch.TRUE if matched else ConditionBranch.FALSE
        return NodeExecutionResult.text(text, selected_handle=branch.value)

    def _read_condition_type(self, context: NodeExecutionContext) -> ConditionType:
        """Read and validate the condition type."""
        raw = context.node_data.get("condition_type")
        try:
            return ConditionType(raw)
        except ValueError as exc:
            message = "Condition node has an unsupported condition_type"
            raise ExecutionGraphValidationError(message=message) from exc

    def _read_case_sensitive(self, context: NodeExecutionContext) -> bool:
        """Read the case-sensitivity flag, defaulting to insensitive."""
        return context.node_data.get("case_sensitive") == "true"


def _build_handler(deps: NodeHandlerDeps) -> ConditionNodeHandler:
    """Build a condition node handler."""
    del deps
    return ConditionNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.CONDITION,
    label="Condition / Router",
    icon_key="condition",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
        output_handles=(ConditionBranch.TRUE.value, ConditionBranch.FALSE.value),
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Condition label",
            ),
            default="Condition node",
        ),
        NodeFieldSpec(
            name="condition_type",
            required=True,
            validators={
                ValidatorType.SELECT.value: [member.value for member in ConditionType]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Condition",
                help="How to evaluate the upstream text.",
            ),
            default=ConditionType.CONTAINS.value,
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
                field="condition_type", not_equals=ConditionType.NOT_EMPTY.value
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
        ),
    ),
    build_handler=_build_handler,
)
