"""Daily digest template: Input(schedule) -> Web Search -> LLM -> Template -> Output.

Fires once a day (default 9am UTC) with no incoming message, so the search
query comes from the Input node's own `scheduled_value` (a scheduled Input
node's fixed fired-with text) rather than `{{input}}` like a chat flow's
prompt would. Edit that field for whatever topic should be digested. The
Template node wraps the LLM's summary in a fixed header/footer before
delivery — demonstrates using Template purely for message formatting rather
than prompt-building. Output defaults to Telegram so the digest actually
reaches someone; pin a chat ID (or provider/bot) after creating it, same as
any node whose reference starts unset.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={
                "label": "Daily Trigger",
                "format": InputNodeFormat.SCHEDULE.value,
                "cron_expression": "0 9 * * *",
                "scheduled_value": "latest AI news",
            },
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.WEB_SEARCH,
            data={"label": "Search", "max_results": 5},
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Summarize",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "Summarize the following search results into a short, "
                    "readable daily digest with a few bullet points."
                ),
            },
            position_x=560.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.TEMPLATE,
            data={
                "label": "Format Digest",
                "template": "📰 *Daily Digest*\n\n{{input}}\n\n_Powered by Graph AI_",
            },
            position_x=840.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={
                "label": "Deliver Digest",
                "format": OutputNodeFormat.TELEGRAM.value,
                "telegram_bot_id": None,
                "telegram_chat_id": None,
            },
            position_x=1120.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=2, source_handle=None),
        WorkflowGraphEdge(source_index=2, target_index=3, source_handle=None),
        WorkflowGraphEdge(source_index=3, target_index=4, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="daily-digest",
    name="Daily Digest",
    description=(
        'Fires every day at 9am UTC, searches for "latest AI news" (edit '
        "the Input node's Value field for your own topic), and delivers an "
        "LLM-summarized digest over Telegram. Pick a provider and bot, and "
        "pin a chat ID on the Output node, after creating it."
    ),
    category="Automation",
    setup_steps=(
        "Choose an LLM provider and model.",
        "Choose a Telegram bot and destination chat.",
    ),
    graph=_GRAPH,
)
