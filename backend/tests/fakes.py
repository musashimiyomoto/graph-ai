"""In-memory Qdrant test double, shared by node-handler and API tests.

Avoids needing a real Qdrant server or a fastembed model download in tests
that exercise the RAG ingest pipeline (Vector Ingest/Search nodes, Vector
Collections API).
"""

from types import SimpleNamespace
from typing import Any

from qdrant_client.http.models import Filter


class _FakePoint:
    """Minimal stand-in for a Qdrant ScoredPoint."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store the point's payload."""
        self.payload = payload


class _FakeQueryResponse:
    """Minimal stand-in for a Qdrant QueryResponse."""

    def __init__(self, points: list[_FakePoint]) -> None:
        """Store the response's points."""
        self.points = points


class FakeQdrantClient:
    """In-memory stand-in for `AsyncQdrantClient`."""

    def __init__(self) -> None:
        """Start with no collections."""
        self.collections: dict[str, list[tuple[list[float], dict[str, Any]]]] = {}

    async def collection_exists(self, name: str) -> bool:
        """Report whether a collection has been created."""
        return name in self.collections

    async def create_collection(
        self, collection_name: str, vectors_config: object
    ) -> None:
        """Create an empty collection if it doesn't exist yet."""
        del vectors_config
        self.collections.setdefault(collection_name, [])

    async def upsert(self, collection_name: str, points: list[Any]) -> None:
        """Append each point's vector/payload to the collection."""
        store = self.collections.setdefault(collection_name, [])
        for point in points:
            store.append((point.vector, point.payload))

    async def query_points(
        self,
        collection_name: str,
        query: list[float],
        limit: int,
        query_filter: Filter | None = None,
    ) -> _FakeQueryResponse:
        """Return the first `limit` stored points, ignoring the query vector."""
        del query
        store = self.collections.get(collection_name, [])
        conditions = getattr(query_filter, "must", None) or []

        def matches(payload: dict[str, Any]) -> bool:
            for condition in conditions:
                match = condition.match
                expected = getattr(match, "value", None)
                if expected is not None and payload.get(condition.key) != expected:
                    return False
                allowed = getattr(match, "any", None)
                if allowed is not None and payload.get(condition.key) not in allowed:
                    return False
            return True

        points = [_FakePoint(payload) for _, payload in store if matches(payload)][
            :limit
        ]
        return _FakeQueryResponse(points)

    async def get_collections(self, **kwargs: object) -> SimpleNamespace:
        """List every collection name."""
        del kwargs
        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in self.collections]
        )

    async def get_collection(
        self, collection_name: str, **kwargs: object
    ) -> SimpleNamespace:
        """Return the point count for a collection."""
        del kwargs
        points = self.collections.get(collection_name, [])
        return SimpleNamespace(points_count=len(points))

    async def scroll(
        self, collection_name: str, *, with_payload: object = True, **kwargs: object
    ) -> tuple[list[SimpleNamespace], None]:
        """Return every point in one page (test collections are tiny)."""
        del with_payload, kwargs
        store = self.collections.get(collection_name, [])
        return [SimpleNamespace(payload=payload) for _, payload in store], None

    async def delete(
        self, collection_name: str, points_selector: Filter, **kwargs: object
    ) -> None:
        """Delete points matching a `Filter`'s `must` field conditions."""
        del kwargs
        store = self.collections.get(collection_name)
        if store is None:
            return
        conditions = getattr(points_selector, "must", None) or []
        self.collections[collection_name] = [
            (vector, payload)
            for vector, payload in store
            if not all(payload.get(c.key) == c.match.value for c in conditions)
        ]

    async def set_payload(
        self,
        collection_name: str,
        payload: dict[str, Any],
        points: Filter,
        **kwargs: object,
    ) -> None:
        """Merge payload fields into points matching a source filter."""
        del kwargs
        store = self.collections.get(collection_name, [])
        conditions = getattr(points, "must", None) or []
        for _, existing in store:
            if all(existing.get(c.key) == c.match.value for c in conditions):
                existing.update(payload)

    async def delete_collection(self, collection_name: str, **kwargs: object) -> bool:
        """Delete a collection outright."""
        del kwargs
        return self.collections.pop(collection_name, None) is not None

    async def close(self) -> None:
        """No-op: nothing to release."""
