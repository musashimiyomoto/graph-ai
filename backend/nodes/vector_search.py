"""Vector Search node handler.

Embeds the upstream text (treated as a query) locally via fastembed and
returns the top-k most similar chunks previously stored by a Vector Ingest
node into the same Qdrant collection, joined into a single text block meant
to feed downstream nodes (e.g. as LLM context).
"""

from asyncio import to_thread

from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError, VectorCollectionNotFoundError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from nodes.rendering import upstream_text
from rag.embeddings import embed_texts
from rag.qdrant import get_qdrant_client
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
)
from usecases.vector import VectorUsecase

_MIN_TOP_K = 1
_MAX_TOP_K = 20


class VectorSearchNodeHandler:
    """Handler for vector-search nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Embed the upstream query and return the top-k matching chunks.

        Args:
            context: Node execution context.

        Returns:
            The matched chunks' text, joined by a separator. Empty string
            if the collection has no matches.

        Raises:
            ExecutionGraphValidationError: If the collection field is
                missing, the query text is empty, top_k is out of range, or
                the collection doesn't exist yet.

        """
        collection = context.node_data.get("collection")
        if not isinstance(collection, str) or not collection.strip():
            message = "Vector Search node requires a non-empty collection name"
            raise ExecutionGraphValidationError(message=message)

        top_k = context.node_data.get("top_k")
        if not isinstance(top_k, int) or not (_MIN_TOP_K <= top_k <= _MAX_TOP_K):
            message = (
                f"Vector Search node requires top_k to be an integer in "
                f"[{_MIN_TOP_K}, {_MAX_TOP_K}]"
            )
            raise ExecutionGraphValidationError(message=message)

        query = upstream_text(context).strip()
        if not query:
            message = "Vector Search node received an empty query"
            raise ExecutionGraphValidationError(message=message)

        client = get_qdrant_client()
        try:
            try:
                physical_name, sources = await VectorUsecase(
                    client
                ).resolve_search_collection(
                    session=context.session,
                    user_id=context.workflow_owner_id,
                    name=collection,
                )
            except VectorCollectionNotFoundError as exc:
                message = (
                    f"Collection '{collection}' does not exist — "
                    "ingest documents into it first."
                )
                raise ExecutionGraphValidationError(message=message) from exc
            if not sources:
                return NodeExecutionResult.text(output="")
            (vector,) = await to_thread(embed_texts, [query])
            response = await client.query_points(
                collection_name=physical_name,
                query=vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="owner_id",
                            match=MatchValue(value=context.workflow_owner_id),
                        ),
                        FieldCondition(key="source", match=MatchAny(any=sources)),
                    ]
                ),
                limit=top_k,
            )
            return NodeExecutionResult.text(
                output="\n\n---\n\n".join(
                    str((point.payload or {}).get("text", ""))
                    for point in response.points
                )
            )
        finally:
            await client.close()


def _build_handler(deps: NodeHandlerDeps) -> VectorSearchNodeHandler:
    """Build a vector-search node handler."""
    del deps
    return VectorSearchNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.VECTOR_SEARCH,
    label="Vector Search",
    icon_key="vector_search",
    graph=graph_spec(
        input_type=PortType.TEXT,
        output_type=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Vector Search label",
            ),
            default="Vector Search node",
        ),
        NodeFieldSpec(
            name="collection",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.VECTOR_COLLECTION,
                label="Collection",
                placeholder="my-documents",
                help="Qdrant collection to search, populated by a Vector Ingest node.",
            ),
            datasource=NodeFieldDataSource(
                kind=NodeFieldDataSourceKind.VECTOR_COLLECTION
            ),
            default="",
        ),
        NodeFieldSpec(
            name="top_k",
            required=True,
            validators={
                ValidatorType.GE.value: _MIN_TOP_K,
                ValidatorType.LE.value: _MAX_TOP_K,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.NUMBER,
                label="Top K",
                help="How many matching chunks to return.",
                step=1,
            ),
            default=4,
        ),
    ),
    build_handler=_build_handler,
)
