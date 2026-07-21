"""Vector Ingest node handler.

Chunks the upstream text, embeds each chunk locally via fastembed
(``rag.embeddings``), and upserts the chunks into a Qdrant collection
(``rag.ingest``). Pairs with the Vector Search node, which reads back from
the same collection, and with the Vector Collections Settings tab, which
lets a document ingested here be browsed/deleted (and lets documents be
uploaded directly, bypassing the graph). Collection names are free text and
shared globally — no per-user/per-workflow namespacing.
"""

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from nodes.rendering import upstream_text
from rag.ingest import ingest_document
from rag.qdrant import get_qdrant_client
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)


class VectorIngestNodeHandler:
    """Handler for vector-ingest nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Chunk, embed, and store the upstream text in a Qdrant collection.

        Args:
            context: Node execution context.

        Returns:
            A confirmation message with the number of chunks stored.

        Raises:
            ExecutionGraphValidationError: If the collection field is
                missing, or the upstream text is empty.

        """
        collection = context.node_data.get("collection")
        if not isinstance(collection, str) or not collection.strip():
            message = "Vector Ingest node requires a non-empty collection name"
            raise ExecutionGraphValidationError(message=message)

        source = context.node_data.get("source")
        if not isinstance(source, str) or not source.strip():
            label = context.node_data.get("label")
            source = label if isinstance(label, str) and label.strip() else "untitled"

        client = get_qdrant_client()
        try:
            chunks_ingested = await ingest_document(
                client=client,
                collection=collection,
                text=upstream_text(context),
                source=source,
            )
        finally:
            await client.close()

        if chunks_ingested == 0:
            message = "Vector Ingest node received no text to ingest"
            raise ExecutionGraphValidationError(message=message)

        return NodeExecutionResult.text(
            output=f"Ingested {chunks_ingested} chunk(s) into '{collection}'."
        )


def _build_handler(deps: NodeHandlerDeps) -> VectorIngestNodeHandler:
    """Build a vector-ingest node handler."""
    del deps
    return VectorIngestNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.VECTOR_INGEST,
    label="Vector Ingest",
    icon_key="vector_ingest",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Vector Ingest label",
            ),
            default="Vector Ingest node",
        ),
        NodeFieldSpec(
            name="collection",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.VECTOR_COLLECTION,
                label="Collection",
                placeholder="my-documents",
                help="Qdrant collection to store chunks in. Pick an existing "
                "one or type a new name to create it.",
            ),
            datasource=NodeFieldDataSource(
                kind=NodeFieldDataSourceKind.VECTOR_COLLECTION
            ),
            default="",
        ),
        NodeFieldSpec(
            name="source",
            required=False,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Source (optional)",
                placeholder="Defaults to this node's label",
                help="Identifies this document. Re-running the node with "
                "the same source replaces its chunks instead of "
                "duplicating them.",
            ),
            default="",
        ),
    ),
    build_handler=_build_handler,
)
