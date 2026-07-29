"""Simple chatbot template: Input -> LLM -> Output.

The minimal working flow — one LLM call over the raw input text. The
llm_provider_id is left unset (same as any freshly imported graph); the user
picks their provider in the node inspector after creating the workflow.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat, TemplateSettingsSection
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Input", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Assistant",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": "You are a helpful assistant.",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": OutputNodeFormat.TXT.value},
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
    key="simple-chatbot",
    name="Simple Chatbot",
    description=(
        "A minimal chat flow: your message goes straight to an LLM and its "
        "reply comes back as output. Pick a provider after creating it."
    ),
    category="AI & Text",
    setup_steps=(
        "Add an LLM provider in Settings -> LLM Providers.",
        "Select the Assistant node and choose its provider and model.",
    ),
    settings_sections=(TemplateSettingsSection.PROVIDERS,),
    graph=_GRAPH,
)
