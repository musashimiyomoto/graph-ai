"""Weather bot template: Input(city) -> HTTP Request -> LLM -> Output.

Calls wttr.in's plain-text endpoint, which needs no API key/signup, so this
one actually works the moment a provider is picked — no other reference to
pin first. Demonstrates HTTP Request's `{{input}}` URL substitution feeding
straight into an LLM for a bit of natural-language framing.
"""

from enums import HttpMethod, InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "City", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.HTTP_REQUEST,
            data={
                "label": "Fetch Weather",
                "method": HttpMethod.GET.value,
                "url": "https://wttr.in/{{input}}?format=3",
                "headers": None,
                "body": "",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Add Commentary",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "You'll be given a one-line weather report. Reply with "
                    "a short, friendly comment (1-2 sentences) suggesting "
                    "what to wear or do today based on it."
                ),
            },
            position_x=560.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Forecast", "format": OutputNodeFormat.TXT.value},
            position_x=840.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=2, source_handle=None),
        WorkflowGraphEdge(source_index=2, target_index=3, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="weather-bot",
    name="Weather Bot",
    description=(
        "Send a city name and get its current weather (via the free, "
        "keyless wttr.in API) plus a short LLM comment on what to wear. "
        "Pick a provider on the Add Commentary node after creating it."
    ),
    graph=_GRAPH,
)
