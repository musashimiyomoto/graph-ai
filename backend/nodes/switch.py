"""Switch node definition and dynamic branch validation."""

import re
from dataclasses import dataclass
from typing import Any

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from nodes.rendering import upstream_text
from schemas import NodeFieldSpec, NodeFieldUI, NodeFieldWidget

DEFAULT_SWITCH_HANDLE = "default"
MIN_SWITCH_BRANCHES = 1
MAX_SWITCH_BRANCHES = 8
_BRANCH_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class SwitchConfigurationError(ValueError):
    """Raised when persisted Switch branch configuration is malformed."""


@dataclass(frozen=True)
class SwitchBranch:
    """One ordered Switch comparison and its output handle."""

    name: str
    value: str


def parse_switch_branches(node_data: dict[str, Any]) -> tuple[SwitchBranch, ...]:
    """Parse and strictly validate ordered Switch branches.

    Args:
        node_data: Persisted node configuration.

    Returns:
        Validated branches in matching order.

    Raises:
        SwitchConfigurationError: If branch configuration is malformed.

    """
    raw_branches = node_data.get("branches")
    if not isinstance(raw_branches, list):
        message = "Switch branches must be a list"
        raise SwitchConfigurationError(message)
    if not MIN_SWITCH_BRANCHES <= len(raw_branches) <= MAX_SWITCH_BRANCHES:
        message = (
            f"Switch requires between {MIN_SWITCH_BRANCHES} and "
            f"{MAX_SWITCH_BRANCHES} branches"
        )
        raise SwitchConfigurationError(message)

    branches: list[SwitchBranch] = []
    seen_names: set[str] = set()
    for index, raw_branch in enumerate(raw_branches, start=1):
        if not isinstance(raw_branch, dict):
            message = f"Switch branch {index} must be an object"
            raise SwitchConfigurationError(message)
        if set(raw_branch) != {"name", "value"}:
            message = f"Switch branch {index} must contain only name and value"
            raise SwitchConfigurationError(message)

        name = raw_branch.get("name")
        value = raw_branch.get("value")
        if not isinstance(name, str) or not _BRANCH_NAME_PATTERN.fullmatch(name):
            message = f"Switch branch {index} name must match ^[a-z][a-z0-9_-]{{0,31}}$"
            raise SwitchConfigurationError(message)
        if name == DEFAULT_SWITCH_HANDLE:
            message = "'default' is reserved and cannot be a Switch branch name"
            raise SwitchConfigurationError(message)
        if name in seen_names:
            message = f"Switch branch name '{name}' is duplicated"
            raise SwitchConfigurationError(message)
        if not isinstance(value, str) or not value.strip():
            message = f"Switch branch '{name}' requires a non-empty value"
            raise SwitchConfigurationError(message)

        seen_names.add(name)
        branches.append(SwitchBranch(name=name, value=value))

    return tuple(branches)


def switch_output_handles(node_data: dict[str, Any]) -> tuple[str, ...]:
    """Return configured branch handles followed by the default fallback."""
    return (
        *(branch.name for branch in parse_switch_branches(node_data)),
        DEFAULT_SWITCH_HANDLE,
    )


def select_switch_handle(node_data: dict[str, Any], text: str) -> str:
    """Return the first exact-match branch handle or the default fallback."""
    branches = parse_switch_branches(node_data)
    case_sensitive = node_data.get("case_sensitive") == "true"
    comparable_text = text if case_sensitive else text.casefold()
    for branch in branches:
        comparable_value = branch.value if case_sensitive else branch.value.casefold()
        if comparable_text == comparable_value:
            return branch.name
    return DEFAULT_SWITCH_HANDLE


class SwitchNodeHandler:
    """Route upstream text to the first matching named branch."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Select the first exact-value match or the default fallback."""
        text = upstream_text(context)
        try:
            selected_handle = select_switch_handle(context.node_data, text)
        except SwitchConfigurationError as exc:
            raise ExecutionGraphValidationError(message=str(exc)) from exc

        return NodeExecutionResult.text(text, selected_handle=selected_handle)


def _build_handler(deps: NodeHandlerDeps) -> SwitchNodeHandler:
    """Build a Switch node handler."""
    del deps
    return SwitchNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.SWITCH,
    label="Switch",
    icon_key="switch",
    graph=graph_spec(
        input_type=PortType.TEXT,
        output_type=PortType.TEXT,
        output_handles=(DEFAULT_SWITCH_HANDLE,),
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Switch label",
            ),
            default="Switch node",
        ),
        NodeFieldSpec(
            name="branches",
            required=True,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SWITCH_BRANCHES,
                label="Branches",
                help=(
                    "Exact matches are checked in order. Unmatched values use "
                    "the default output."
                ),
            ),
            default=({"name": "branch_1", "value": "value"},),
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
