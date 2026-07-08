"""Vector Collections use case implementation (browse/delete/upload documents)."""

from qdrant_client import AsyncQdrantClient

from constants import MAX_DOCUMENT_UPLOAD_BYTES
from exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    VectorCollectionNotFoundError,
    VectorDocumentNotFoundError,
)
from rag.documents import extract_text
from rag.ingest import ingest_document
from rag.qdrant import (
    delete_by_source,
    delete_collection,
    get_collection_point_count,
    list_collections,
    list_sources,
)
from schemas import (
    VectorCollectionResponse,
    VectorDocumentResponse,
    VectorUploadResponse,
)


class VectorUsecase:
    """Vector Collections business logic."""

    def __init__(self, client: AsyncQdrantClient) -> None:
        """Initialize the usecase with a request-scoped Qdrant client."""
        self._client = client

    async def list_collections(self) -> list[VectorCollectionResponse]:
        """List every Qdrant collection with its total chunk count.

        Returns:
            One entry per collection.

        """
        names = await list_collections(self._client)
        return [
            VectorCollectionResponse(
                name=name,
                point_count=await get_collection_point_count(self._client, name),
            )
            for name in names
        ]

    async def list_documents(self, collection: str) -> list[VectorDocumentResponse]:
        """List each document (source) in a collection with its chunk count.

        Args:
            collection: Collection to inspect.

        Returns:
            One entry per document, sorted by source.

        Raises:
            VectorCollectionNotFoundError: If the collection doesn't exist.

        """
        await self._require_collection(collection)
        sources = await list_sources(self._client, collection)
        return [
            VectorDocumentResponse(source=source, chunk_count=count)
            for source, count in sorted(sources.items())
        ]

    async def delete_document(self, collection: str, source: str) -> None:
        """Delete every chunk belonging to one document.

        Args:
            collection: Collection the document lives in.
            source: The document's identifier.

        Raises:
            VectorCollectionNotFoundError: If the collection doesn't exist.
            VectorDocumentNotFoundError: If no chunks match this source.

        """
        await self._require_collection(collection)
        sources = await list_sources(self._client, collection)
        if source not in sources:
            raise VectorDocumentNotFoundError
        await delete_by_source(self._client, collection, source)

    async def delete_collection(self, collection: str) -> None:
        """Delete a collection outright.

        Args:
            collection: Collection to delete.

        Raises:
            VectorCollectionNotFoundError: If the collection doesn't exist.

        """
        await self._require_collection(collection)
        await delete_collection(self._client, collection)

    async def upload_document(
        self,
        collection: str,
        filename: str,
        content: bytes,
        source_override: str | None,
    ) -> VectorUploadResponse:
        """Extract, chunk, embed, and store an uploaded document.

        Args:
            collection: Collection to store chunks in. Created if missing.
            filename: The uploaded file's original name.
            content: The file's raw bytes.
            source_override: Document identifier to use instead of
                `filename`, if provided.

        Returns:
            The document's identifier and how many chunks were stored.

        Raises:
            DocumentTooLargeError: If `content` exceeds the size cap.
            UnsupportedDocumentTypeError: If the file can't be parsed.
            EmptyDocumentError: If it parses to no extractable text.

        """
        if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
            raise DocumentTooLargeError

        text = extract_text(filename, content)
        source = (
            source_override.strip()
            if source_override and source_override.strip()
            else filename
        )
        chunks_ingested = await ingest_document(
            client=self._client, collection=collection, text=text, source=source
        )
        if chunks_ingested == 0:
            raise EmptyDocumentError

        return VectorUploadResponse(source=source, chunks_ingested=chunks_ingested)

    async def _require_collection(self, collection: str) -> None:
        """Raise if a collection doesn't exist.

        Args:
            collection: Collection to check.

        Raises:
            VectorCollectionNotFoundError: If it doesn't exist.

        """
        if not await self._client.collection_exists(collection):
            raise VectorCollectionNotFoundError
