"""Vector Collections API tests."""

from http import HTTPStatus

import pytest
import pytest_asyncio
from httpx import AsyncClient

from api.dependencies import qdrant
from main import app
from schemas import VectorJobStatusResponse
from tests.fakes import FakeQdrantClient
from tests.test_api.base import BaseTestCase


class VectorTestCase(BaseTestCase):
    """Base class giving each test a fresh in-memory Qdrant client."""

    @pytest_asyncio.fixture(autouse=True)
    async def _fake_qdrant(self, test_client: AsyncClient) -> None:
        """Swap the test suite's no-op Qdrant client for a working fake."""
        del test_client
        self.qdrant_client = FakeQdrantClient()
        app.dependency_overrides[qdrant.get_qdrant_client] = lambda: self.qdrant_client


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
        _, headers = await self.create_user_and_get_token()
        self.qdrant_client.collections["docs"] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-a"}),
        ]

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        if data != [{"name": "docs", "point_count": 2}]:
            pytest.fail("Unexpected collection list")


class TestVectorDocumentsList(VectorTestCase):
    """Tests for GET /vector-collections/{collection}/documents."""

    @pytest.mark.asyncio
    async def test_groups_by_source(self) -> None:
        """Documents are grouped by source with a chunk count each."""
        _, headers = await self.create_user_and_get_token()
        self.qdrant_client.collections["docs"] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-a"}),
            ([3.0], {"text": "c", "source": "doc-b"}),
        ]

        response = await self.client.get(
            url="/vector-collections/docs/documents", headers=headers
        )

        data = await self.assert_response_list(response=response)
        if data != [
            {"source": "doc-a", "chunk_count": 2},
            {"source": "doc-b", "chunk_count": 1},
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
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url="/vector-collections/docs/documents",
            headers=headers,
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )

        if response.status_code != HTTPStatus.ACCEPTED:
            pytest.fail("Expected a 202 Accepted for a queued upload")
        data = await self.assert_response_dict(response=response)
        if not data["job_id"]:
            pytest.fail("Expected a job id in the response")
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
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url="/vector-collections/jobs/some-job", headers=headers
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
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url="/vector-collections/jobs/some-job", headers=headers
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != "failed" or data["detail"] != "boom":
            pytest.fail("Expected the failure detail to be returned")


class TestVectorDocumentDelete(VectorTestCase):
    """Tests for DELETE /vector-collections/{collection}/documents/{source}."""

    @pytest.mark.asyncio
    async def test_deletes_only_matching_source(self) -> None:
        """Deleting a document removes only its chunks."""
        _, headers = await self.create_user_and_get_token()
        self.qdrant_client.collections["docs"] = [
            ([1.0], {"text": "a", "source": "doc-a"}),
            ([2.0], {"text": "b", "source": "doc-b"}),
        ]

        response = await self.client.delete(
            url="/vector-collections/docs/documents/doc-a", headers=headers
        )

        await self.assert_response_ok(response=response)
        remaining = [
            payload["source"] for _, payload in self.qdrant_client.collections["docs"]
        ]
        if remaining != ["doc-b"]:
            pytest.fail("Expected only the targeted document's chunks to be removed")

    @pytest.mark.asyncio
    async def test_unknown_document_404s(self) -> None:
        """A source with no chunks returns 404."""
        _, headers = await self.create_user_and_get_token()
        self.qdrant_client.collections["docs"] = [
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
        _, headers = await self.create_user_and_get_token()
        self.qdrant_client.collections["docs"] = [
            ([1.0], {"text": "a", "source": "doc-a"})
        ]

        response = await self.client.delete(
            url="/vector-collections/docs", headers=headers
        )

        await self.assert_response_ok(response=response)
        if "docs" in self.qdrant_client.collections:
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
