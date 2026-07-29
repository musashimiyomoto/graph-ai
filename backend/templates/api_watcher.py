"""API watcher template: Input(schedule, every 5 min) -> HTTP Request -> Output.

Polls a GET endpoint on a tight cron interval with no incoming message (the
request needs no `{{input}}`), and forwards the raw response body over
Telegram. Edit the URL/headers on the HTTP Request node for the endpoint to
watch, and the cron expression on the Input node for how often.
"""

from enums import HttpMethod, InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={
                "label": "Every 5 Minutes",
                "format": InputNodeFormat.SCHEDULE.value,
                "cron_expression": "*/5 * * * *",
                "scheduled_value": "",
            },
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.HTTP_REQUEST,
            data={
                "label": "Check Endpoint",
                "method": HttpMethod.GET.value,
                "url": "https://api.example.com/status",
                "headers": None,
                "body": "",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={
                "label": "Notify",
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
    key="api-watcher",
    name="API Watcher",
    description=(
        "Polls a URL every 5 minutes (edit the cron expression to change "
        "the interval) and delivers the raw response over Telegram. Edit "
        "the HTTP Request node's URL/headers for the endpoint to watch, "
        "and pin a provider/bot/chat ID after creating it."
    ),
    category="Automation",
    setup_steps=(
        "Set the endpoint URL and any required headers.",
        "Choose a Telegram bot and destination chat.",
    ),
    graph=_GRAPH,
)
