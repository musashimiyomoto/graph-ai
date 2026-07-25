"""Tenant-safe knowledge collection and revisioned source business logic."""

import hashlib
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from qdrant_client import AsyncQdrantClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from constants import MAX_DOCUMENT_UPLOAD_BYTES
from db.models import KnowledgeCollection, KnowledgeSource
from db.repositories import (
    KnowledgeCollectionRepository,
    KnowledgeSourceRepository,
)
from exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    VectorCollectionNotFoundError,
    VectorDocumentNotFoundError,
)
from rag.documents import extract_text
from rag.ingest import ChunkPayload, ingest_document
from rag.qdrant import (
    delete_by_source,
    delete_collection,
    get_collection_point_count,
    update_source_payload,
)
from schemas import (
    KnowledgeACL,
    KnowledgeIngestOptions,
    KnowledgeUploadTask,
    VectorCollectionResponse,
    VectorDocumentResponse,
    VectorSyncStateUpdate,
    VectorUploadResponse,
)
from usecases.audit import AuditEvent, AuditUsecase

_RETENTION_BATCH_SIZE = 100
_MAX_COLLECTION_NAME_LENGTH = 255


def _physical_collection_name(owner_id: int, name: str) -> str:
    """Build an opaque deterministic Qdrant namespace for one tenant/name pair."""
    digest = hashlib.sha256(name.encode()).hexdigest()[:32]
    return f"tenant_{owner_id}_{digest}"


def _source_response(source: KnowledgeSource) -> VectorDocumentResponse:
    """Serialize durable source metadata for owner-facing APIs."""
    return VectorDocumentResponse(
        source=source.source,
        chunk_count=source.chunk_count,
        source_type=source.source_type,
        external_id=source.external_id,
        revision=source.revision,
        content_hash=source.content_hash,
        acl=KnowledgeACL.model_validate(source.acl),
        metadata=source.source_metadata,
        expires_at=source.expires_at,
        last_synced_at=source.last_synced_at,
    )


class VectorUsecase:
    """Manage owner-scoped collections, source revisions, and retention."""

    def __init__(self, client: AsyncQdrantClient) -> None:
        """Initialize Qdrant and SQL repository dependencies."""
        self._client = client
        self._collection_repository = KnowledgeCollectionRepository()
        self._source_repository = KnowledgeSourceRepository()
        self._audit_usecase = AuditUsecase()

    async def prepare_collection(
        self, *, session: AsyncSession, user_id: int, name: str
    ) -> KnowledgeCollection:
        """Create or return one owner-scoped logical collection mapping."""
        normalized = self._normalize_collection_name(name)
        await self._lock_collection(session=session, user_id=user_id, name=normalized)
        collection = await self._collection_repository.get_by(
            session=session, owner_id=user_id, name=normalized
        )
        if collection is not None:
            return collection
        return await self._collection_repository.create(
            session=session,
            data={
                "owner_id": user_id,
                "name": normalized,
                "physical_name": _physical_collection_name(user_id, normalized),
            },
        )

    async def list_collections(
        self, *, session: AsyncSession, user_id: int
    ) -> list[VectorCollectionResponse]:
        """List only the caller's logical collections and physical point counts."""
        collections = await self._collection_repository.get_all(
            session=session, owner_id=user_id
        )
        responses: list[VectorCollectionResponse] = []
        for collection in collections:
            point_count = 0
            if await self._client.collection_exists(collection.physical_name):
                point_count = await get_collection_point_count(
                    self._client, collection.physical_name
                )
            responses.append(
                VectorCollectionResponse(
                    name=collection.name,
                    point_count=point_count,
                    sync_cursor=collection.sync_cursor,
                    last_synced_at=collection.last_synced_at,
                )
            )
        return responses

    async def list_documents(
        self, *, session: AsyncSession, user_id: int, collection: str
    ) -> list[VectorDocumentResponse]:
        """List non-expired source metadata inside an owned collection."""
        owned = await self._require_collection(
            session=session, user_id=user_id, name=collection
        )
        sources = await self._source_repository.list_active(
            session=session, collection_id=owned.id, now=datetime.now(tz=UTC)
        )
        return [_source_response(source) for source in sources]

    async def upload_document(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        task: KnowledgeUploadTask,
    ) -> VectorUploadResponse:
        """Extract and ingest an uploaded owner-scoped document."""
        if len(task.content) > MAX_DOCUMENT_UPLOAD_BYTES:
            raise DocumentTooLargeError
        text = extract_text(task.filename, task.content)
        source = (
            task.source.strip()
            if task.source and task.source.strip()
            else task.filename
        )
        return await self.ingest_text(
            session=session,
            user_id=user_id,
            collection=task.collection,
            text=text,
            source=source,
            options=task.options,
        )

    async def ingest_text(  # noqa: PLR0913
        self,
        *,
        session: AsyncSession,
        user_id: int,
        collection: str,
        text: str,
        source: str,
        options: KnowledgeIngestOptions,
    ) -> VectorUploadResponse:
        """Upsert one source revision, skipping identical incremental updates."""
        normalized_source = source.strip()
        if not normalized_source:
            raise EmptyDocumentError(message="Knowledge source key cannot be empty")
        owned = await self.prepare_collection(
            session=session, user_id=user_id, name=collection
        )
        now = datetime.now(tz=UTC)
        content_hash = hashlib.sha256(text.strip().encode()).hexdigest()
        existing = await self._source_repository.get_by(
            session=session,
            collection_id=owned.id,
            source=normalized_source,
        )
        expires_at = (
            now + timedelta(days=options.retention_days)
            if options.retention_days is not None and options.retention_days > 0
            else None
        )
        unchanged = existing is not None and (
            existing.content_hash == content_hash
            or (options.revision is not None and existing.revision == options.revision)
        )
        if existing is not None and unchanged and not options.force:
            if await self._client.collection_exists(owned.physical_name):
                await update_source_payload(
                    self._client,
                    owned.physical_name,
                    normalized_source,
                    {
                        "source_type": options.source_type,
                        "external_id": options.external_id,
                        "revision": options.revision,
                        "acl": options.acl.model_dump(),
                        "metadata": options.metadata,
                        "expires_at": (
                            expires_at.isoformat() if expires_at is not None else None
                        ),
                        "ingested_at": now.isoformat(),
                    },
                )
            await self._update_source_metadata(
                session=session,
                source=existing,
                options=options,
                expires_at=expires_at,
                now=now,
            )
            self._update_collection_sync(collection=owned, options=options, now=now)
            await session.commit()
            return VectorUploadResponse(
                source=normalized_source,
                chunks_ingested=existing.chunk_count,
                unchanged=True,
            )

        chunks_ingested = await ingest_document(
            client=self._client,
            collection=owned.physical_name,
            text=text,
            source=normalized_source,
            payload=ChunkPayload(
                owner_id=user_id,
                logical_collection=owned.name,
                source_type=options.source_type,
                external_id=options.external_id,
                revision=options.revision,
                content_hash=content_hash,
                acl=options.acl.model_dump(),
                metadata=options.metadata,
                expires_at=expires_at,
            ),
        )
        if chunks_ingested == 0:
            raise EmptyDocumentError

        source_data = {
            "owner_id": user_id,
            "collection_id": owned.id,
            "source": normalized_source,
            "source_type": options.source_type,
            "external_id": options.external_id,
            "revision": options.revision,
            "content_hash": content_hash,
            "acl": options.acl.model_dump(),
            "source_metadata": options.metadata,
            "chunk_count": chunks_ingested,
            "expires_at": expires_at,
            "last_synced_at": now,
        }
        if existing is None:
            source_row = await self._source_repository.create(
                session=session, data=source_data
            )
        else:
            source_row = await self._source_repository.update_by(
                session=session, id=existing.id, data=source_data
            )
            if source_row is None:
                raise VectorDocumentNotFoundError
        self._update_collection_sync(collection=owned, options=options, now=now)
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="knowledge_source.ingest",
                entity_type="knowledge_source",
                entity_id=source_row.id,
                metadata={
                    "collection": owned.name,
                    "source": normalized_source,
                    "source_type": options.source_type,
                    "revision": options.revision,
                    "chunks": chunks_ingested,
                },
            ),
        )
        await session.commit()
        return VectorUploadResponse(
            source=normalized_source, chunks_ingested=chunks_ingested
        )

    async def delete_document(
        self, *, session: AsyncSession, user_id: int, collection: str, source: str
    ) -> None:
        """Delete one owned source from Qdrant and its durable registry."""
        owned = await self._require_collection(
            session=session, user_id=user_id, name=collection
        )
        document = await self._source_repository.get_by(
            session=session, collection_id=owned.id, source=source
        )
        if document is None:
            raise VectorDocumentNotFoundError
        if await self._client.collection_exists(owned.physical_name):
            await delete_by_source(self._client, owned.physical_name, source)
        await self._source_repository.delete_by(session=session, id=document.id)
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="knowledge_source.delete",
                entity_type="knowledge_source",
                entity_id=document.id,
                metadata={"collection": owned.name, "source": source},
            ),
        )
        await session.commit()

    async def delete_collection(
        self, *, session: AsyncSession, user_id: int, collection: str
    ) -> None:
        """Delete one owned logical and physical collection."""
        owned = await self._require_collection(
            session=session, user_id=user_id, name=collection
        )
        if await self._client.collection_exists(owned.physical_name):
            await delete_collection(self._client, owned.physical_name)
        await self._collection_repository.delete_by(session=session, id=owned.id)
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="knowledge_collection.delete",
                entity_type="knowledge_collection",
                entity_id=owned.id,
                metadata={"collection": owned.name},
            ),
        )
        await session.commit()

    async def update_sync_state(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        collection: str,
        data: VectorSyncStateUpdate,
    ) -> VectorCollectionResponse:
        """Persist a connector cursor after one successful incremental page."""
        owned = await self._require_collection(
            session=session, user_id=user_id, name=collection
        )
        owned.sync_cursor = data.sync_cursor
        owned.last_synced_at = datetime.now(tz=UTC)
        await session.commit()
        await session.refresh(owned)
        point_count = 0
        if await self._client.collection_exists(owned.physical_name):
            point_count = await get_collection_point_count(
                self._client, owned.physical_name
            )
        return VectorCollectionResponse(
            name=owned.name,
            point_count=point_count,
            sync_cursor=owned.sync_cursor,
            last_synced_at=owned.last_synced_at,
        )

    async def resolve_search_collection(
        self, *, session: AsyncSession, user_id: int, name: str
    ) -> tuple[str, list[str]]:
        """Resolve an owned physical name and currently retained source keys."""
        owned = await self._require_collection(
            session=session, user_id=user_id, name=name
        )
        if not await self._client.collection_exists(owned.physical_name):
            raise VectorCollectionNotFoundError
        sources = await self._source_repository.list_active(
            session=session, collection_id=owned.id, now=datetime.now(tz=UTC)
        )
        return owned.physical_name, [source.source for source in sources]

    async def cleanup_expired(self, *, session: AsyncSession) -> int:
        """Delete one bounded batch of expired source metadata and chunks."""
        expired = await self._source_repository.list_expired(
            session=session,
            now=datetime.now(tz=UTC),
            limit=_RETENTION_BATCH_SIZE,
        )
        for source in expired:
            collection = await self._collection_repository.get_by(
                session=session, id=source.collection_id
            )
            if collection is not None and await self._client.collection_exists(
                collection.physical_name
            ):
                await delete_by_source(
                    self._client, collection.physical_name, source.source
                )
            await self._source_repository.delete_by(session=session, id=source.id)
        await session.commit()
        return len(expired)

    async def _require_collection(
        self, *, session: AsyncSession, user_id: int, name: str
    ) -> KnowledgeCollection:
        """Return one owned logical mapping without exposing other tenants."""
        collection = await self._collection_repository.get_by(
            session=session,
            owner_id=user_id,
            name=self._normalize_collection_name(name),
        )
        if collection is None:
            raise VectorCollectionNotFoundError
        return collection

    @staticmethod
    async def _lock_collection(
        *, session: AsyncSession, user_id: int, name: str
    ) -> None:
        """Serialize creation while the owner/name mapping has no row to lock."""
        material = f"knowledge:{user_id}:{name}".encode()
        lock_key = int.from_bytes(
            hashlib.sha256(material).digest()[:8], byteorder="big", signed=True
        )
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    @staticmethod
    def _normalize_collection_name(name: str) -> str:
        """Normalize and bound owner-visible collection names."""
        normalized = name.strip()
        if not normalized or len(normalized) > _MAX_COLLECTION_NAME_LENGTH:
            raise VectorCollectionNotFoundError(
                message="Collection name must contain 1 to 255 characters",
                status_code=HTTPStatus.BAD_REQUEST,
            )
        return normalized

    async def _update_source_metadata(
        self,
        *,
        session: AsyncSession,
        source: KnowledgeSource,
        options: KnowledgeIngestOptions,
        expires_at: datetime | None,
        now: datetime,
    ) -> None:
        """Refresh metadata for a skipped identical source revision."""
        await self._source_repository.update_by(
            session=session,
            id=source.id,
            data={
                "source_type": options.source_type,
                "external_id": options.external_id,
                "revision": options.revision,
                "acl": options.acl.model_dump(),
                "source_metadata": options.metadata,
                "expires_at": expires_at,
                "last_synced_at": now,
            },
        )

    @staticmethod
    def _update_collection_sync(
        *,
        collection: KnowledgeCollection,
        options: KnowledgeIngestOptions,
        now: datetime,
    ) -> None:
        """Advance an optional opaque cursor atomically with source metadata."""
        collection.last_synced_at = now
        if options.sync_cursor is not None:
            collection.sync_cursor = options.sync_cursor
