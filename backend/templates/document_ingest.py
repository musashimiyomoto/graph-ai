"""Document ingest template: Input -> Vector Ingest -> Output.

Paste a document's text as a chat message to embed and store it in the RAG
"documents" collection — an alternative to the Settings -> Vector
Collections upload UI for adding content on the fly. Pairs with the RAG
Chatbot template, which queries the same collection.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_COLLECTION_NAME = "documents"

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Document Text", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.VECTOR_INGEST,
            data={
                "label": "Ingest into RAG",
                "collection": _COLLECTION_NAME,
                "source": "",
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Confirmation", "format": OutputNodeFormat.TXT.value},
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
    key="document-ingest",
    name="Document Ingest",
    description=(
        "Paste a document as a message to chunk, embed, and store it in "
        f'the "{_COLLECTION_NAME}" collection — the same one the RAG '
        "Chatbot template queries. No provider needed."
    ),
    graph=_GRAPH,
)
