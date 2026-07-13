"""Input node handler."""

from enums import InputNodeFormat, NodeType, PortType, ValidatorType
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
    NodeGraphSpec,
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
    graph=NodeGraphSpec(
        has_input=False,
        has_output=True,
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
                placeholder="Input label",
            ),
            default="Input node",
        ),
        NodeFieldSpec(
            name="format",
            required=True,
            validators={
                ValidatorType.SELECT.value: [member.value for member in InputNodeFormat]
            },
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
            default=InputNodeFormat.TXT.value,
        ),
        NodeFieldSpec(
            name="telegram_bot_id",
            required=False,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TELEGRAM_BOT,
                label="Telegram Bot",
                help="The bot to poll for messages.",
            ),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.TELEGRAM_BOT),
            visible_when=NodeFieldVisibility(
                field="format", equals=InputNodeFormat.TELEGRAM.value
            ),
        ),
        NodeFieldSpec(
            name="cron_expression",
            required=False,
            validators={ValidatorType.CRON.value: True},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Schedule (cron)",
                placeholder="0 9 * * *",
                help="Standard 5-field cron expression, evaluated in UTC.",
            ),
            visible_when=NodeFieldVisibility(
                field="format", equals=InputNodeFormat.SCHEDULE.value
            ),
        ),
        NodeFieldSpec(
            name="scheduled_value",
            required=False,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Value",
                placeholder="latest AI news",
                help=(
                    "A scheduled run has no incoming message, so this fixed "
                    "text is used as the input value each time it fires. "
                    "Leave blank to fire with an empty value."
                ),
            ),
            default="",
            visible_when=NodeFieldVisibility(
                field="format", equals=InputNodeFormat.SCHEDULE.value
            ),
        ),
    ),
    build_handler=_build_handler,
)
