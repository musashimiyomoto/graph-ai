"""Quick translate template: Input -> Translate -> Output."""

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Source Text", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.TRANSLATE,
            data={
                "label": "Translate to English",
                "service": "google",
                "target_language": "English",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Translation", "format": OutputNodeFormat.TXT.value},
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
    key="quick-translate",
    name="Quick Translate",
    description=(
        "Translates pasted text to English with a free, keyless translation "
        "service. Change the language or service on Translate to English."
    ),
    category="Utilities",
    setup_steps=(),
    settings_sections=(),
    graph=_GRAPH,
)
