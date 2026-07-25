"""Durable Delay / Wait node definition and wake-up time parsing."""

from datetime import UTC, datetime, timedelta

from constants import MAX_DELAY_SECONDS
from enums import DelayMode, DelayUnit, NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
)

_UNIT_SECONDS = {
    DelayUnit.SECONDS: 1,
    DelayUnit.MINUTES: 60,
    DelayUnit.HOURS: 60 * 60,
    DelayUnit.DAYS: 24 * 60 * 60,
}


def resolve_wait_until(node_data: dict[str, object], now: datetime) -> datetime:
    """Resolve and validate a Delay node's absolute UTC wake-up time.

    Args:
        node_data: Persisted Delay node configuration.
        now: Current timezone-aware time.

    Returns:
        The requested wake-up time normalized to UTC.

    Raises:
        ExecutionGraphValidationError: If the configuration is invalid or
            requests a wait longer than the global cap.

    """
    if now.tzinfo is None:
        raise ExecutionGraphValidationError(
            message="Delay clock must be timezone-aware"
        )

    try:
        mode = DelayMode(node_data.get("mode"))
    except (TypeError, ValueError) as exc:
        raise ExecutionGraphValidationError(
            message="Delay node requires a supported mode"
        ) from exc

    if mode is DelayMode.DURATION:
        return _resolve_duration(node_data=node_data, now=now)
    return _resolve_timestamp(node_data=node_data, now=now)


def _resolve_duration(node_data: dict[str, object], now: datetime) -> datetime:
    """Resolve duration-mode configuration."""
    duration = node_data.get("duration")
    if not isinstance(duration, int | float) or isinstance(duration, bool):
        raise ExecutionGraphValidationError(message="Delay duration must be a number")
    try:
        unit = DelayUnit(node_data.get("unit"))
    except (TypeError, ValueError) as exc:
        raise ExecutionGraphValidationError(
            message="Delay node requires a supported duration unit"
        ) from exc
    seconds = float(duration) * _UNIT_SECONDS[unit]
    if seconds < 1 or seconds > MAX_DELAY_SECONDS:
        message = f"Delay duration must be between 1 and {MAX_DELAY_SECONDS} seconds"
        raise ExecutionGraphValidationError(message=message)
    return now.astimezone(UTC) + timedelta(seconds=seconds)


def _resolve_timestamp(node_data: dict[str, object], now: datetime) -> datetime:
    """Resolve absolute-timestamp mode configuration."""
    raw_timestamp = node_data.get("timestamp")
    if not isinstance(raw_timestamp, str) or not raw_timestamp.strip():
        raise ExecutionGraphValidationError(
            message="Delay until mode requires an ISO 8601 timestamp"
        )
    try:
        target = datetime.fromisoformat(raw_timestamp.strip())
    except ValueError as exc:
        raise ExecutionGraphValidationError(
            message="Delay timestamp must be valid ISO 8601"
        ) from exc
    if target.tzinfo is None or target.utcoffset() is None:
        raise ExecutionGraphValidationError(
            message="Delay timestamp must include a timezone offset or Z"
        )

    target = target.astimezone(UTC)
    if (target - now.astimezone(UTC)).total_seconds() > MAX_DELAY_SECONDS:
        raise ExecutionGraphValidationError(
            message="Delay timestamp cannot be more than 30 days in the future"
        )
    return target


class DelayNodeHandler:
    """Placeholder handler; the graph runner owns durable pause/resume state."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Reject direct dispatch because durable waiting needs lifecycle access."""
        del context
        raise ExecutionGraphValidationError(
            message="Delay node must be executed by the graph runner"
        )


def _build_handler(deps: NodeHandlerDeps) -> DelayNodeHandler:
    """Build the Delay registry placeholder handler."""
    del deps
    return DelayNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.DELAY,
    label="Delay / Wait",
    icon_key="delay",
    graph=graph_spec(
        input_type=PortType.TEXT,
        output_type=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(widget=NodeFieldWidget.TEXT, label="Label"),
            default="Delay / Wait",
        ),
        NodeFieldSpec(
            name="mode",
            required=True,
            validators={ValidatorType.SELECT.value: tuple(DelayMode)},
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Wait mode"),
            default=DelayMode.DURATION,
        ),
        NodeFieldSpec(
            name="duration",
            required=True,
            validators={
                ValidatorType.GE.value: 1,
                ValidatorType.LE.value: MAX_DELAY_SECONDS,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.NUMBER,
                label="Duration",
                step=1,
                help="The combined duration and unit cannot exceed 30 days.",
            ),
            default=1,
            visible_when=NodeFieldVisibility(field="mode", equals=DelayMode.DURATION),
        ),
        NodeFieldSpec(
            name="unit",
            required=True,
            validators={ValidatorType.SELECT.value: tuple(DelayUnit)},
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Unit"),
            default=DelayUnit.MINUTES,
            visible_when=NodeFieldVisibility(field="mode", equals=DelayMode.DURATION),
        ),
        NodeFieldSpec(
            name="timestamp",
            required=True,
            validators={ValidatorType.DATETIME.value: True},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Wait until",
                placeholder="2026-07-21T09:00:00+03:00",
                help=(
                    "ISO 8601 timestamp with a timezone offset or Z; "
                    "at most 30 days ahead."
                ),
            ),
            default="",
            visible_when=NodeFieldVisibility(field="mode", equals=DelayMode.UNTIL),
        ),
    ),
    build_handler=_build_handler,
)
