"""Tests for the background document-ingest worker task."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import worker as worker_module
from db.models import KnowledgeCollection, KnowledgeSource
from exceptions import EmptyDocumentError, UnsupportedDocumentTypeError
from schemas import KnowledgeACL, KnowledgeIngestOptions, KnowledgeUploadTask
from tests.factories import (
    KnowledgeCollectionFactory,
    KnowledgeSourceFactory,
    UserFactory,
)
from tests.fakes import FakeQdrantClient
from usecases import VectorUsecase

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic fake embedding: a single feature, the text length."""
    return [[float(len(text))] for text in texts]


@pytest.fixture
def fake_qdrant(monkeypatch: pytest.MonkeyPatch) -> FakeQdrantClient:
    """Route the worker task's Qdrant client and embeddings to in-memory fakes."""
    client = FakeQdrantClient()
    monkeypatch.setattr(worker_module, "get_qdrant_client", lambda: client)
    monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
    return client


@pytest.fixture
async def owner_id(
    monkeypatch: pytest.MonkeyPatch,
    test_session: AsyncSession,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Create an owner and bind worker sessions to the isolated test database."""
    user = await UserFactory.create_async(session=test_session)
    monkeypatch.setattr(worker_module, "async_session", test_session_factory)
    return user.id


def _task(
    *,
    owner_id: int,
    content: bytes,
    source: str | None = None,
    filename: str = "notes.txt",
    options: KnowledgeIngestOptions | None = None,
) -> dict[str, object]:
    """Build one serialized worker ingestion payload."""
    return KnowledgeUploadTask(
        owner_id=owner_id,
        collection="docs",
        filename=filename,
        content=content,
        source=source,
        options=options or KnowledgeIngestOptions(),
    ).model_dump(mode="python")


async def test_ingest_stores_chunks(
    fake_qdrant: FakeQdrantClient, owner_id: int
) -> None:
    """The task ingests a text file under its filename and returns the count."""
    result = await worker_module.ingest_document_task(
        {}, _task(owner_id=owner_id, content=b"hello world")
    )

    if result != {"source": "notes.txt", "chunks_ingested": 1, "unchanged": False}:
        pytest.fail("Expected one chunk ingested under the filename")
    physical_name = next(iter(fake_qdrant.collections))
    if len(fake_qdrant.collections[physical_name]) != 1:
        pytest.fail("Expected the chunk to be stored in Qdrant")


async def test_source_override(fake_qdrant: FakeQdrantClient, owner_id: int) -> None:
    """An explicit source overrides the filename."""
    del fake_qdrant
    result = await worker_module.ingest_document_task(
        {}, _task(owner_id=owner_id, content=b"hello world", source="custom-name")
    )

    if result["source"] != "custom-name":
        pytest.fail("Expected the source override to take precedence")


async def test_reupload_same_source_replaces(
    fake_qdrant: FakeQdrantClient, owner_id: int
) -> None:
    """Re-ingesting the same source replaces its chunks instead of appending."""
    await worker_module.ingest_document_task(
        {}, _task(owner_id=owner_id, content=b"hello world")
    )
    await worker_module.ingest_document_task(
        {}, _task(owner_id=owner_id, content=b"a different body")
    )

    physical_name = next(iter(fake_qdrant.collections))
    if len(fake_qdrant.collections[physical_name]) != 1:
        pytest.fail("Re-ingesting the same source should replace, not append")


async def test_unsupported_binary_rejected(
    fake_qdrant: FakeQdrantClient, owner_id: int
) -> None:
    """A file that isn't valid UTF-8 text and isn't PDF/DOCX raises."""
    del fake_qdrant
    with pytest.raises(UnsupportedDocumentTypeError):
        await worker_module.ingest_document_task(
            {},
            _task(
                owner_id=owner_id,
                content=b"\x89PNG\r\n\x1a\n\x00\x01",
                filename="image.png",
            ),
        )


async def test_empty_document_rejected(
    fake_qdrant: FakeQdrantClient, owner_id: int
) -> None:
    """A file with no extractable text raises."""
    del fake_qdrant
    with pytest.raises(EmptyDocumentError):
        await worker_module.ingest_document_task(
            {}, _task(owner_id=owner_id, content=b"   ", filename="empty.txt")
        )


async def test_revision_acl_retention_and_cursor_are_persisted(
    fake_qdrant: FakeQdrantClient,
    owner_id: int,
    test_session: AsyncSession,
) -> None:
    """Connector metadata is durable and duplicated onto every Qdrant chunk."""
    result = await worker_module.ingest_document_task(
        {},
        _task(
            owner_id=owner_id,
            content=b"versioned knowledge",
            options=KnowledgeIngestOptions(
                source_type="notion",
                external_id="page-42",
                revision="etag-v1",
                acl=KnowledgeACL(visibility="shared", readers=["team:research"]),
                retention_days=7,
                sync_cursor="cursor-next",
                metadata={"space": "engineering"},
            ),
        ),
    )
    if result["unchanged"]:
        pytest.fail("First source revision was incorrectly skipped")

    source = await test_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.owner_id == owner_id)
    )
    collection = await test_session.scalar(
        select(KnowledgeCollection).where(KnowledgeCollection.owner_id == owner_id)
    )
    if source is None or collection is None:
        pytest.fail("Knowledge metadata was not persisted")
        return
    if (
        source.source_type != "notion"
        or source.external_id != "page-42"
        or source.revision != "etag-v1"
        or source.acl["readers"] != ["team:research"]
        or source.expires_at is None
        or collection.sync_cursor != "cursor-next"
    ):
        pytest.fail("Knowledge source metadata was not persisted correctly")
    payload = fake_qdrant.collections[collection.physical_name][0][1]
    if (
        payload["owner_id"] != owner_id
        or payload["revision"] != "etag-v1"
        or payload["acl"]["visibility"] != "shared"
    ):
        pytest.fail("Qdrant payload omitted tenant/revision/ACL metadata")


async def test_identical_revision_skips_reembedding(
    fake_qdrant: FakeQdrantClient, owner_id: int
) -> None:
    """A connector retry with the same revision leaves existing chunks intact."""
    options = KnowledgeIngestOptions(source_type="drive", revision="revision-1")
    await worker_module.ingest_document_task(
        {}, _task(owner_id=owner_id, content=b"original", options=options)
    )
    result = await worker_module.ingest_document_task(
        {},
        _task(
            owner_id=owner_id,
            content=b"retry body",
            options=KnowledgeIngestOptions(
                source_type="drive",
                revision="revision-1",
                acl=KnowledgeACL(visibility="shared", readers=["user:reader"]),
            ),
        ),
    )

    if not result["unchanged"]:
        pytest.fail("An identical provider revision was re-embedded")
    physical_name = next(iter(fake_qdrant.collections))
    points = fake_qdrant.collections[physical_name]
    if len(points) != 1 or points[0][1]["text"] != "original":
        pytest.fail("An unchanged revision replaced the stored chunks")
    if points[0][1]["acl"]["readers"] != ["user:reader"]:
        pytest.fail("A metadata-only retry did not update Qdrant ACL payload")


async def test_retention_cleanup_removes_metadata_and_chunks(
    fake_qdrant: FakeQdrantClient,
    owner_id: int,
    test_session: AsyncSession,
) -> None:
    """Expired sources are removed from both persistence layers."""
    collection = await KnowledgeCollectionFactory.create_async(
        session=test_session,
        owner_id=owner_id,
        name="retained",
        physical_name=f"tenant_{owner_id}_retained",
    )
    source = await KnowledgeSourceFactory.create_async(
        session=test_session,
        owner_id=owner_id,
        collection_id=collection.id,
        source="expired",
        expires_at=datetime.now(tz=UTC) - timedelta(minutes=1),
    )
    fake_qdrant.collections[collection.physical_name] = [
        ([1.0], {"text": "old", "source": "expired", "owner_id": owner_id})
    ]

    cleaned = await VectorUsecase(
        cast("AsyncQdrantClient", fake_qdrant)
    ).cleanup_expired(session=test_session)

    if cleaned != 1:
        pytest.fail("Retention cleanup did not report the expired source")
    if await test_session.get(KnowledgeSource, source.id) is not None:
        pytest.fail("Expired source metadata was not deleted")
    if fake_qdrant.collections[collection.physical_name]:
        pytest.fail("Expired Qdrant chunks were not deleted")
