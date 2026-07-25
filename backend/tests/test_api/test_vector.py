"""Vector Collections API tests."""

from http import HTTPStatus

import pytest
import pytest_asyncio
from httpx import AsyncClient

from api.dependencies import qdrant
from db.models import KnowledgeCollection
from main import app
from schemas import VectorJobStatusResponse
from tests.factories import KnowledgeCollectionFactory, KnowledgeSourceFactory
from tests.fakes import FakeQdrantClient
from tests.test_api.base import BaseTestCase

_EXPECTED_POINT_COUNT = 2


class VectorTestCase(BaseTestCase):
    """Base class giving each test a fresh in-memory Qdrant client."""

    @pytest_asyncio.fixture(autouse=True)
    async def _fake_qdrant(self, test_client: AsyncClient) -> None:
        """Swap the test suite's no-op Qdrant client for a working fake."""
        del test_client
        self.qdrant_client = FakeQdrantClient()
        app.dependency_overrides[qdrant.get_qdrant_client] = lambda: self.qdrant_client

    async def create_collection(
        self, *, owner_id: int, name: str = "docs"
    ) -> KnowledgeCollection:
        """Persist one logical collection for the current fake Qdrant client."""
        return await KnowledgeCollectionFactory.create_async(
            session=self.session,
            owner_id=owner_id,
            name=name,
            physical_name=f"tenant_{owner_id}_{name}",
        )


class TestVectorCollectionsList(VectorTestCase):
    """Tests for GET /vector-collections."""

    url = "/vector-collections"

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        """No collections yet returns an empty list."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        if data:
            pytest.fail("Expected an empty list")

    @pytest.mark.asyncio
    async def test_lists_point_counts(self) -> None:
        """Collections list with their chunk counts."""
        user, headers = await self.create_user_and_get_token()
        collection = await self.create_collection(owner_id=user["id"])
        self.qdrant_client.collections[collection.physical_name] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-a"}),
        ]

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        if (
            len(data) != 1
            or data[0]["name"] != "docs"
            or data[0]["point_count"] != _EXPECTED_POINT_COUNT
        ):
            pytest.fail("Unexpected collection list")

    @pytest.mark.asyncio
    async def test_same_logical_name_is_isolated_by_owner(self) -> None:
        """Two tenants can use one logical name without sharing physical data."""
        first, first_headers = await self.create_user_and_get_token()
        second, second_headers = await self.create_user_and_get_token()
        first_collection = await self.create_collection(owner_id=first["id"])
        second_collection = await self.create_collection(owner_id=second["id"])
        self.qdrant_client.collections[first_collection.physical_name] = [
            ([1.0], {"text": "first", "owner_id": first["id"]})
        ]
        self.qdrant_client.collections[second_collection.physical_name] = [
            ([2.0], {"text": "second", "owner_id": second["id"]}),
            ([3.0], {"text": "second-2", "owner_id": second["id"]}),
        ]

        first_response = await self.client.get(url=self.url, headers=first_headers)
        second_response = await self.client.get(url=self.url, headers=second_headers)
        first_data = await self.assert_response_list(response=first_response)
        second_data = await self.assert_response_list(response=second_response)
        if (
            first_data[0]["point_count"] != 1
            or second_data[0]["point_count"] != _EXPECTED_POINT_COUNT
        ):
            pytest.fail("Logical collection names crossed tenant namespaces")


class TestVectorDocumentsList(VectorTestCase):
    """Tests for GET /vector-collections/{collection}/documents."""

    @pytest.mark.asyncio
    async def test_groups_by_source(self) -> None:
        """Documents are grouped by source with a chunk count each."""
        user, headers = await self.create_user_and_get_token()
        collection = await self.create_collection(owner_id=user["id"])
        await KnowledgeSourceFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            collection_id=collection.id,
            source="doc-a",
            chunk_count=2,
        )
        await KnowledgeSourceFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            collection_id=collection.id,
            source="doc-b",
            chunk_count=1,
        )
        self.qdrant_client.collections[collection.physical_name] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-a"}),
            ([3.0], {"text": "c", "source": "doc-b"}),
        ]

        response = await self.client.get(
            url="/vector-collections/docs/documents", headers=headers
        )

        data = await self.assert_response_list(response=response)
        if [(item["source"], item["chunk_count"]) for item in data] != [
            ("doc-a", 2),
            ("doc-b", 1),
        ]:
            pytest.fail("Unexpected document grouping")

    @pytest.mark.asyncio
    async def test_unknown_collection_404s(self) -> None:
        """A collection that was never created returns 404."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url="/vector-collections/missing/documents", headers=headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected a 404 for an unknown collection")


class TestVectorDocumentUpload(VectorTestCase):
    """Tests for POST /vector-collections/{collection}/documents.

    Ingestion now runs on the ARQ worker, so the endpoint only accepts the file
    and returns a job id — it no longer ingests inline. The heavy pipeline is
    exercised at the worker level in ``test_worker_ingest.py``.
    """

    @pytest.mark.asyncio
    async def test_upload_enqueues_job(self) -> None:
        """Uploading returns 202 with a job id and the filename as source."""
        user, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url="/vector-collections/docs/documents",
            headers=headers,
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )

        if response.status_code != HTTPStatus.ACCEPTED:
            pytest.fail("Expected a 202 Accepted for a queued upload")
        data = await self.assert_response_dict(response=response)
        if not data["job_id"].startswith(f"knowledge:{user['id']}:"):
            pytest.fail("Expected an owner-scoped job id in the response")
        if data["source"] != "notes.txt":
            pytest.fail("Expected the filename to be used as the source")

    @pytest.mark.asyncio
    async def test_custom_source_override(self) -> None:
        """A `source` form field overrides the filename in the response."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url="/vector-collections/docs/documents",
            headers=headers,
            files={"file": ("notes.txt", b"hello world", "text/plain")},
            data={"source": "custom-name"},
        )

        data = await self.assert_response_dict(response=response)
        if data["source"] != "custom-name":
            pytest.fail("Expected the source override to take precedence")

    @pytest.mark.asyncio
    async def test_oversize_file_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file larger than the cap is rejected before it reaches the queue."""
        monkeypatch.setattr("api.routers.vector.MAX_DOCUMENT_UPLOAD_BYTES", 4)
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url="/vector-collections/docs/documents",
            headers=headers,
            files={"file": ("big.txt", b"way too many bytes", "text/plain")},
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected a 400 for an oversize document")


class TestVectorJobStatus(VectorTestCase):
    """Tests for GET /vector-collections/jobs/{job_id}."""

    @pytest.mark.asyncio
    async def test_returns_mapped_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The endpoint returns whatever the job-status reader reports."""
        expected_chunks = 3

        async def _fake_status(pool: object, job_id: str) -> VectorJobStatusResponse:
            del pool, job_id
            return VectorJobStatusResponse(
                status="ready", chunks_ingested=expected_chunks
            )

        monkeypatch.setattr("api.routers.vector.read_ingest_job_status", _fake_status)
        user, headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url=f"/vector-collections/jobs/knowledge:{user['id']}:some-job",
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != "ready" or data["chunks_ingested"] != expected_chunks:
            pytest.fail("Expected the mapped job status to be returned")

    @pytest.mark.asyncio
    async def test_reports_failure_detail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed job surfaces its detail message."""

        async def _fake_status(pool: object, job_id: str) -> VectorJobStatusResponse:
            del pool, job_id
            return VectorJobStatusResponse(status="failed", detail="boom")

        monkeypatch.setattr("api.routers.vector.read_ingest_job_status", _fake_status)
        user, headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url=f"/vector-collections/jobs/knowledge:{user['id']}:some-job",
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != "failed" or data["detail"] != "boom":
            pytest.fail("Expected the failure detail to be returned")

    @pytest.mark.asyncio
    async def test_other_tenant_job_is_hidden(self) -> None:
        """Authenticated users cannot probe another tenant's ingest job."""
        owner, _ = await self.create_user_and_get_token()
        _, other_headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url=f"/vector-collections/jobs/knowledge:{owner['id']}:opaque",
            headers=other_headers,
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Another tenant could probe an ingest job")


class TestVectorSyncState(VectorTestCase):
    """Tests for PATCH /vector-collections/{collection}/sync-state."""

    @pytest.mark.asyncio
    async def test_updates_owned_cursor(self) -> None:
        """Connectors can checkpoint an opaque incremental-sync cursor."""
        user, headers = await self.create_user_and_get_token()
        await self.create_collection(owner_id=user["id"])

        response = await self.client.patch(
            url="/vector-collections/docs/sync-state",
            headers=headers,
            json={"sync_cursor": "next-page-token"},
        )

        data = await self.assert_response_dict(response=response)
        if data["sync_cursor"] != "next-page-token" or not data["last_synced_at"]:
            pytest.fail("Incremental sync cursor was not checkpointed")


class TestVectorDocumentDelete(VectorTestCase):
    """Tests for DELETE /vector-collections/{collection}/documents/{source}."""

    @pytest.mark.asyncio
    async def test_deletes_only_matching_source(self) -> None:
        """Deleting a document removes only its chunks."""
        user, headers = await self.create_user_and_get_token()
        collection = await self.create_collection(owner_id=user["id"])
        await KnowledgeSourceFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            collection_id=collection.id,
            source="doc-a",
        )
        await KnowledgeSourceFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            collection_id=collection.id,
            source="doc-b",
        )
        self.qdrant_client.collections[collection.physical_name] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-b"}),
        ]

        response = await self.client.delete(
            url="/vector-collections/docs/documents/doc-a", headers=headers
        )

        await self.assert_response_ok(response=response)
        remaining = [
            payload["source"]
            for _, payload in self.qdrant_client.collections[collection.physical_name]
        ]
        if remaining != ["doc-b"]:
            pytest.fail("Expected only the targeted document's chunks to be removed")

    @pytest.mark.asyncio
    async def test_unknown_document_404s(self) -> None:
        """A source with no chunks returns 404."""
        user, headers = await self.create_user_and_get_token()
        collection = await self.create_collection(owner_id=user["id"])
        await KnowledgeSourceFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            collection_id=collection.id,
            source="doc-a",
        )
        self.qdrant_client.collections[collection.physical_name] = [
            ([1.0], {"text": "a", "source": "doc-a"})
        ]

        response = await self.client.delete(
            url="/vector-collections/docs/documents/missing", headers=headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected a 404 for an unknown document")


class TestVectorCollectionDelete(VectorTestCase):
    """Tests for DELETE /vector-collections/{collection}."""

    @pytest.mark.asyncio
    async def test_deletes_collection(self) -> None:
        """Deleting a collection removes it entirely."""
        user, headers = await self.create_user_and_get_token()
        collection = await self.create_collection(owner_id=user["id"])
        self.qdrant_client.collections[collection.physical_name] = [
            ([1.0], {"text": "a", "source": "doc-a"})
        ]

        response = await self.client.delete(
            url="/vector-collections/docs", headers=headers
        )

        await self.assert_response_ok(response=response)
        if collection.physical_name in self.qdrant_client.collections:
            pytest.fail("Expected the collection to be gone")

    @pytest.mark.asyncio
    async def test_unknown_collection_404s(self) -> None:
        """Deleting a collection that doesn't exist returns 404."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.delete(
            url="/vector-collections/missing", headers=headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected a 404 for an unknown collection")
