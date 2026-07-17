"""Output node handler."""

from enums import NodeType, OutputNodeFormat, PortType, ValidatorType
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


class OutputNodeHandler:
    """Handler for output nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Join upstream values into final output."""
        return NodeExecutionResult(output="\n".join(context.parent_values))


def _build_handler(deps: NodeHandlerDeps) -> OutputNodeHandler:
    """Build an output node handler."""
    del deps
    return OutputNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.OUTPUT,
    label="Output",
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
                placeholder="Output label",
            ),
            default="Output node",
        ),
        NodeFieldSpec(
            name="format",
            required=True,
            validators={
                ValidatorType.SELECT.value: [
                    member.value for member in OutputNodeFormat
                ]
            },
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
            default=OutputNodeFormat.TXT.value,
        ),
        NodeFieldSpec(
            name="telegram_bot_id",
            required=False,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TELEGRAM_BOT,
                label="Telegram Bot",
                help="The bot to reply through.",
            ),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.TELEGRAM_BOT),
            visible_when=NodeFieldVisibility(
                field="format", equals=OutputNodeFormat.TELEGRAM.value
            ),
        ),
        NodeFieldSpec(
            name="telegram_chat_id",
            required=False,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.OPTIONAL_NUMBER,
                label="Telegram Chat ID",
                help=(
                    "Optional. Pin a fixed destination chat so this also works "
                    "for manual (non-Telegram-triggered) runs. Leave blank to "
                    "reply to whichever chat triggered the run."
                ),
                step=1,
            ),
            visible_when=NodeFieldVisibility(
                field="format", equals=OutputNodeFormat.TELEGRAM.value
            ),
        ),
        NodeFieldSpec(
            name="email_account_id",
            required=False,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.EMAIL_ACCOUNT,
                label="Email Account",
                help="The SMTP account used to send the result.",
            ),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.EMAIL_ACCOUNT),
            visible_when=NodeFieldVisibility(
                field="format", equals=OutputNodeFormat.EMAIL.value
            ),
        ),
        NodeFieldSpec(
            name="email_to",
            required=False,
            validators={ValidatorType.MIN_LENGTH.value: 0},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="To",
                placeholder="recipient@example.com",
                help=(
                    "Optional fixed recipient. Leave blank to reply to the sender "
                    "that triggered the run."
                ),
            ),
            visible_when=NodeFieldVisibility(
                field="format", equals=OutputNodeFormat.EMAIL.value
            ),
        ),
        NodeFieldSpec(
            name="email_subject",
            required=False,
            validators={ValidatorType.MIN_LENGTH.value: 0},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Subject",
                placeholder="Workflow result",
                help=(
                    "Optional fixed subject. Replies use the incoming subject "
                    "when blank."
                ),
            ),
            visible_when=NodeFieldVisibility(
                field="format", equals=OutputNodeFormat.EMAIL.value
            ),
        ),
    ),
    build_handler=_build_handler,
)
