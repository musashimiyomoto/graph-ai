"""Shared chunk/embed/upsert pipeline.

Used by both the Vector Ingest node and the Vector Collections upload
endpoint.
"""

from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointStruct

from rag.embeddings import embed_texts
from rag.qdrant import chunk_text, delete_by_source, ensure_collection


@dataclass(frozen=True)
class ChunkPayload:
    """Source metadata duplicated onto every Qdrant chunk."""

    owner_id: int
    logical_collection: str
    source_type: str
    external_id: str | None
    revision: str | None
    content_hash: str
    acl: dict
    metadata: dict
    expires_at: datetime | None


async def ingest_document(
    client: AsyncQdrantClient,
    collection: str,
    text: str,
    source: str,
    *,
    payload: ChunkPayload,
) -> int:
    """Chunk, embed, and store a document's text under a given source.

    Any chunks already stored under the same `(collection, source)` are
    deleted first, so re-ingesting a document replaces its chunks instead of
    appending duplicates alongside stale ones.

    Args:
        client: Qdrant client.
        collection: Collection to store chunks in. Created if missing.
        text: The document's full text.
        source: Identifies this document within the collection — reused to
            replace its chunks on a later re-ingest.
        payload: Source metadata duplicated into each chunk for filtering.

    Returns:
        The number of chunks ingested (0 if `text` had no content to chunk).

    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    vectors = await to_thread(embed_texts, chunks)
    await ensure_collection(client, collection, vector_size=len(vectors[0]))
    await delete_by_source(client, collection, source)
    await client.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=str(uuid4()),
                vector=vector,
                payload={
                    "text": chunk,
                    "owner_id": payload.owner_id,
                    "collection": payload.logical_collection,
                    "source": source,
                    "source_type": payload.source_type,
                    "external_id": payload.external_id,
                    "revision": payload.revision,
                    "content_hash": payload.content_hash,
                    "acl": payload.acl,
                    "metadata": payload.metadata,
                    "expires_at": (
                        payload.expires_at.isoformat() if payload.expires_at else None
                    ),
                    "ingested_at": datetime.now(tz=UTC).isoformat(),
                    "chunk_index": index,
                    "chunk_count": len(chunks),
                },
            )
            for index, (vector, chunk) in enumerate(zip(vectors, chunks, strict=True))
        ],
    )
    return len(chunks)
