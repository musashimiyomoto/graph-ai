"""Qdrant access helpers.

Shared by the Vector Ingest/Search node handlers and the Vector Collections
API (browse/delete/upload).
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    VectorParams,
)

from settings import rag_settings

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100
_SCROLL_PAGE_SIZE = 500


def get_qdrant_client() -> AsyncQdrantClient:
    """Build a fresh Qdrant client from global settings.

    A generous explicit timeout replaces the client's ~5s default — first-time
    collection creation can take longer than that under I/O contention, and a
    client-side timeout there surfaces as a 500 even though the server-side
    operation went on to succeed.
    """
    return AsyncQdrantClient(
        host=rag_settings.qdrant_host,
        port=rag_settings.qdrant_port,
        timeout=30,
    )


def chunk_text(
    text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP
) -> list[str]:
    """Split text into fixed-size, overlapping character chunks."""
    stripped = text.strip()
    if not stripped:
        return []
    chunks: list[str] = []
    step = size - overlap
    for start in range(0, len(stripped), step):
        chunk = stripped[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(stripped):
            break
    return chunks


async def ensure_collection(
    client: AsyncQdrantClient, name: str, vector_size: int
) -> None:
    """Create the collection with the given vector size if it doesn't exist yet."""
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


async def list_collections(client: AsyncQdrantClient) -> list[str]:
    """List every Qdrant collection name."""
    response = await client.get_collections()
    return [collection.name for collection in response.collections]


async def get_collection_point_count(client: AsyncQdrantClient, name: str) -> int:
    """Return the number of points stored in a collection."""
    info = await client.get_collection(collection_name=name)
    return info.points_count or 0


async def list_sources(client: AsyncQdrantClient, collection: str) -> dict[str, int]:
    """Return each document's `source` and how many chunks it has.

    Scrolls the entire collection (payload only, no vectors) and aggregates
    chunk counts by `source` client-side — fine at the v1 scale this feature
    is scoped to.

    Args:
        client: Qdrant client.
        collection: Collection to scan.

    Returns:
        Mapping of `source` to its chunk count.

    """
    counts: dict[str, int] = {}
    offset = None
    while True:
        points, offset = await client.scroll(
            collection_name=collection,
            limit=_SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=["source"],
            with_vectors=False,
        )
        for point in points:
            source = (point.payload or {}).get("source", "unknown")
            counts[source] = counts.get(source, 0) + 1
        if offset is None:
            break
    return counts


async def delete_by_source(
    client: AsyncQdrantClient, collection: str, source: str
) -> None:
    """Delete every point whose `source` payload field matches."""
    await client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source))]
        ),
    )


async def delete_collection(client: AsyncQdrantClient, name: str) -> None:
    """Delete a Qdrant collection outright."""
    await client.delete_collection(collection_name=name)
