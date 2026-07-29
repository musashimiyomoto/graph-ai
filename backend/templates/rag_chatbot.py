"""RAG chatbot template: Input -> Vector Search -> LLM -> Output.

Deliberately doesn't include a Vector Ingest node: ingesting on every chat
turn would re-embed the same documents repeatedly for no benefit. Populate
the "documents" collection once via the Vector Collections upload UI
(Settings), then use this flow to query it.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_COLLECTION_NAME = "documents"

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={"label": "Question", "format": InputNodeFormat.TXT.value},
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.VECTOR_SEARCH,
            data={
                "label": "Search Documents",
                "collection": _COLLECTION_NAME,
                "top_k": 4,
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Answer",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "Answer the user's question using only the provided "
                    "context. If the context doesn't contain the answer, "
                    "say so."
                ),
            },
            position_x=560.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": OutputNodeFormat.TXT.value},
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
    key="rag-chatbot",
    name="RAG Chatbot",
    description=(
        f'Answers questions from a "{_COLLECTION_NAME}" document collection. '
        "Upload documents to that collection via Settings -> Vector "
        "Collections before using this flow, and pick an LLM provider after "
        "creating it."
    ),
    category="Knowledge",
    setup_steps=(
        "Upload documents to the template's knowledge collection.",
        "Choose an LLM provider and model.",
    ),
    graph=_GRAPH,
)
