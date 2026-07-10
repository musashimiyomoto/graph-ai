"""Tests for the background document-ingest worker task."""

import pytest

import worker as worker_module
from exceptions import EmptyDocumentError, UnsupportedDocumentTypeError
from tests.fakes import FakeQdrantClient


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


async def test_ingest_stores_chunks(fake_qdrant: FakeQdrantClient) -> None:
    """The task ingests a text file under its filename and returns the count."""
    result = await worker_module.ingest_document_task(
        {}, "docs", "notes.txt", b"hello world", None
    )

    if result != {"source": "notes.txt", "chunks_ingested": 1}:
        pytest.fail("Expected one chunk ingested under the filename")
    if len(fake_qdrant.collections["docs"]) != 1:
        pytest.fail("Expected the chunk to be stored in Qdrant")


async def test_source_override(fake_qdrant: FakeQdrantClient) -> None:
    """An explicit source overrides the filename."""
    del fake_qdrant
    result = await worker_module.ingest_document_task(
        {}, "docs", "notes.txt", b"hello world", "custom-name"
    )

    if result["source"] != "custom-name":
        pytest.fail("Expected the source override to take precedence")


async def test_reupload_same_source_replaces(fake_qdrant: FakeQdrantClient) -> None:
    """Re-ingesting the same source replaces its chunks instead of appending."""
    await worker_module.ingest_document_task(
        {}, "docs", "notes.txt", b"hello world", None
    )
    await worker_module.ingest_document_task(
        {}, "docs", "notes.txt", b"a different body", None
    )

    if len(fake_qdrant.collections["docs"]) != 1:
        pytest.fail("Re-ingesting the same source should replace, not append")


async def test_unsupported_binary_rejected(fake_qdrant: FakeQdrantClient) -> None:
    """A file that isn't valid UTF-8 text and isn't PDF/DOCX raises."""
    del fake_qdrant
    with pytest.raises(UnsupportedDocumentTypeError):
        await worker_module.ingest_document_task(
            {}, "docs", "image.png", b"\x89PNG\r\n\x1a\n\x00\x01", None
        )


async def test_empty_document_rejected(fake_qdrant: FakeQdrantClient) -> None:
    """A file with no extractable text raises."""
    del fake_qdrant
    with pytest.raises(EmptyDocumentError):
        await worker_module.ingest_document_task({}, "docs", "empty.txt", b"   ", None)
