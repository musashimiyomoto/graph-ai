"""Support ticket router template: Input -> Condition -> two LLM branches -> Output.

Demonstrates the Condition/Router node's true/false branching and the
execution engine's fan-in: both LLM branches feed the same Output node, but
only the branch the Condition actually selected produces a live parent value
for it — the other is recorded as SKIPPED and contributes nothing (see
`ExecutionUsecase._resolve_live_parents`).
"""

from enums import ConditionType, InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Customer Message", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=140.0,
        ),
        WorkflowGraphNode(
            type=NodeType.CONDITION,
            data={
                "label": "Urgency Check",
                "condition_type": ConditionType.REGEX.value,
                "value": "urgent|asap|emergency|broken|down|not working",
                "case_sensitive": "false",
            },
            position_x=280.0,
            position_y=140.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Escalate",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "This message has been flagged as urgent. Acknowledge "
                    "the urgency, apologize for the inconvenience, and say "
                    "a specialist will follow up within the hour."
                ),
            },
            position_x=560.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Standard Reply",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "You are a friendly, helpful support assistant. Answer "
                    "the customer's message."
                ),
            },
            position_x=560.0,
            position_y=280.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Reply", "format": OutputNodeFormat.TXT.value},
            position_x=840.0,
            position_y=140.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=2, source_handle="true"),
        WorkflowGraphEdge(source_index=1, target_index=3, source_handle="false"),
        WorkflowGraphEdge(source_index=2, target_index=4, source_handle=None),
        WorkflowGraphEdge(source_index=3, target_index=4, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="support-ticket-router",
    name="Support Ticket Router",
    description=(
        'Flags messages containing words like "urgent" or "broken" and '
        "routes them to an escalation reply; everything else gets a "
        "standard, friendly response. Pick a provider on both LLM nodes "
        "after creating it."
    ),
    graph=_GRAPH,
)
