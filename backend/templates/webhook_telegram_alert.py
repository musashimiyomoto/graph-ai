"""Webhook alert template: Input(webhook) -> Template -> Output(telegram)."""

from enums import (
    InputNodeFormat,
    NodeType,
    OutputNodeFormat,
    TemplateSettingsSection,
)
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Webhook Event", "format": InputNodeFormat.WEBHOOK.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.TEMPLATE,
            data={
                "label": "Format Alert",
                "template": "New webhook event:\n\n{{input}}",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={
                "label": "Send Alert",
                "format": OutputNodeFormat.TELEGRAM.value,
                "telegram_bot_id": None,
                "telegram_chat_id": None,
            },
            position_x=560.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=2, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="webhook-telegram-alert",
    name="Webhook to Telegram Alert",
    description=(
        "Receives a signed public webhook, formats its payload, and sends it "
        "to Telegram. Copy the webhook URL from the workflow menu."
    ),
    category="Channels",
    setup_steps=(
        "Add a bot in Settings -> Telegram Bots.",
        "Select Send Alert and choose the bot and destination chat.",
        "Open the workflow menu and copy its signed webhook URL.",
    ),
    settings_sections=(TemplateSettingsSection.TELEGRAM,),
    graph=_GRAPH,
)
