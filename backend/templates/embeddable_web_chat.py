"""Embeddable web-chat template: Input(web_chat) -> LLM -> Output(web_chat)."""

from enums import InputNodeFormat, NodeType, OutputNodeFormat, TemplateSettingsSection
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Visitor Message", "format": InputNodeFormat.WEB_CHAT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Chat Assistant",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "You are a concise, helpful website assistant. Answer the "
                    "visitor directly and do not mention internal workflow details."
                ),
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Chat Reply", "format": OutputNodeFormat.WEB_CHAT.value},
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
    key="embeddable-web-chat",
    name="Embeddable Web Chat",
    description=(
        "A website chat widget backed by an LLM workflow. Pick a provider, then "
        "copy the embed snippet from the workflow menu."
    ),
    category="Channels",
    setup_steps=(
        "Add an LLM provider in Settings -> LLM Providers.",
        "Select the Chat Assistant node and choose its provider and model.",
        "Open the workflow menu and copy the web-chat embed snippet.",
    ),
    settings_sections=(TemplateSettingsSection.PROVIDERS,),
    graph=_GRAPH,
)
