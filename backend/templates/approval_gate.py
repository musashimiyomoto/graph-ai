"""Approval gate template: Input -> Approval -> Output."""

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Proposed Value", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.APPROVAL,
            data={
                "label": "Human Review",
                "prompt": "Review and approve this value before continuing.",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Approved Value", "format": OutputNodeFormat.TXT.value},
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
    key="approval-gate",
    name="Approval Gate",
    description=(
        "Pauses a run for human approval before passing the value onward. "
        "Use it as a safe starting point for reviewable automations."
    ),
    category="Automation",
    setup_steps=(),
    settings_sections=(),
    graph=_GRAPH,
)
