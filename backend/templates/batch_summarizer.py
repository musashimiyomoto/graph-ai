"""Batch summarizer template: Input(JSON array) -> Loop(list) -> Output.

The input message is a JSON array of items (e.g. article snippets, support
tickets, log lines); the Loop node runs its body once per element and
collects the results back into a JSON array. Demonstrates the list-mode
Loop node: LOOP_INPUT -> LLM -> LOOP_OUTPUT nested inside the Loop's body,
scoped via `parent_index`.
"""

from enums import (
    InputNodeFormat,
    LoopMode,
    NodeType,
    OutputNodeFormat,
    TemplateSettingsSection,
)
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_LOOP_INDEX = 1

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Items", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP,
            data={"label": "Summarize Each", "mode": LoopMode.LIST.value},
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP_INPUT,
            data={"label": "Item"},
            position_x=280.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Summarize",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "Summarize the following item in one short sentence."
                ),
            },
            position_x=560.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP_OUTPUT,
            data={"label": "Summary"},
            position_x=840.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Summaries", "format": OutputNodeFormat.TXT.value},
            position_x=560.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=2, target_index=3, source_handle=None),
        WorkflowGraphEdge(source_index=3, target_index=4, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=5, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="batch-summarizer",
    name="Batch Summarizer",
    description=(
        "Send a JSON array of items (e.g. "
        '["article one...", "article two..."]) and get back a JSON array '
        "of one-sentence LLM summaries, one per item. Pick a provider and "
        "model on the Summarize node after creating it."
    ),
    category="AI & Text",
    setup_steps=(
        "Add an LLM provider in Settings -> LLM Providers.",
        "Open Summarize Each, select the Summarize node, and choose its provider and model.",
    ),
    settings_sections=(TemplateSettingsSection.PROVIDERS,),
    graph=_GRAPH,
)
