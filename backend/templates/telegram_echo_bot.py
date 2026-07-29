"""Telegram echo bot template: Input(telegram) -> LLM -> Output(telegram).

Both Input and Output default to Telegram format with no bot pinned; the
user picks their bot (and an LLM provider) after creating the workflow, same
as any node whose datasource reference starts unset.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat, TemplateSettingsSection
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={
                "label": "Telegram Message",
                "format": InputNodeFormat.TELEGRAM.value,
                "telegram_bot_id": None,
            },
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Assistant",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": "You are a helpful assistant replying over Telegram.",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={
                "label": "Telegram Reply",
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
    key="telegram-echo-bot",
    name="Telegram Echo Bot",
    description=(
        "Polls a Telegram bot for messages and replies via an LLM. Pick "
        "your bot on the Input and Output nodes, and an LLM provider, "
        "after creating it."
    ),
    category="Channels",
    setup_steps=(
        "Add a bot token in Settings -> Telegram Bots.",
        "Select the Telegram Message and Telegram Reply nodes and choose the bot.",
        "Add an LLM provider in Settings -> LLM Providers, then select it on the Assistant node.",
    ),
    settings_sections=(
        TemplateSettingsSection.TELEGRAM,
        TemplateSettingsSection.PROVIDERS,
    ),
    graph=_GRAPH,
)
