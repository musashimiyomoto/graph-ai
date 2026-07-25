"""Text compactor template: Input -> Loop(condition) -> Code/Transform -> Output.

Repeatedly shrinks the input by 30% per iteration until it's down to 40
words, then marks it done; a node after the loop strips that marker before
the final output. Demonstrates the Loop node's condition mode (each
iteration's LOOP_OUTPUT feeds the next iteration's LOOP_INPUT, stopping once
the Loop's own stop condition matches) paired with Code/Transform doing the
actual work — and needs no LLM provider, so it runs immediately after
creation.
"""

from enums import (
    ConditionType,
    InputNodeFormat,
    LoopMode,
    NodeType,
    OutputNodeFormat,
    PortType,
)
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_LOOP_INDEX = 1

_SHRINK_CODE = (
    "words = input.split()\n"
    "if len(words) <= 40:\n"
    "    output = '[DONE] ' + ' '.join(words)\n"
    "else:\n"
    "    keep = max(1, int(len(words) * 0.7))\n"
    "    output = ' '.join(words[:keep])\n"
)

_STRIP_MARKER_CODE = "output = input.replace('[DONE]', '').strip()\n"

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Long Text", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP,
            data={
                "label": "Shrink Until It Fits",
                "mode": LoopMode.CONDITION.value,
                "condition_type": ConditionType.CONTAINS.value,
                "value": "[DONE]",
                "case_sensitive": "false",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP_INPUT,
            data={"label": "Current Text"},
            position_x=280.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.CODE_TRANSFORM,
            data={
                "label": "Shrink",
                "input_type": PortType.TEXT.value,
                "output_type": PortType.TEXT.value,
                "code": _SHRINK_CODE,
            },
            position_x=560.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.LOOP_OUTPUT,
            data={"label": "Shrunk Text"},
            position_x=840.0,
            position_y=160.0,
            parent_index=_LOOP_INDEX,
        ),
        WorkflowGraphNode(
            type=NodeType.CODE_TRANSFORM,
            data={
                "label": "Strip Marker",
                "input_type": PortType.TEXT.value,
                "output_type": PortType.TEXT.value,
                "code": _STRIP_MARKER_CODE,
            },
            position_x=560.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Compact Text", "format": OutputNodeFormat.TXT.value},
            position_x=840.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=2, target_index=3, source_handle=None),
        WorkflowGraphEdge(source_index=3, target_index=4, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=5, source_handle=None),
        WorkflowGraphEdge(source_index=5, target_index=6, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="text-compactor",
    name="Text Compactor",
    description=(
        "Cuts a long paste down to about 40 words by trimming 30% per pass "
        "until it fits, using the Loop node's condition mode. No LLM "
        "provider needed — try it right after creating it."
    ),
    graph=_GRAPH,
)
