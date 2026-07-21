"""Tenant-scoped artifact lifecycle business logic."""

import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artifacts import ArtifactStore
from db.models import User
from db.repositories import ArtifactRepository
from exceptions import (
    ArtifactExpiredError,
    ArtifactNotFoundError,
    ArtifactQuotaExceededError,
    ArtifactStorageError,
    ArtifactTooLargeError,
    EmptyArtifactError,
)
from schemas import (
    ArtifactDownloadResponse,
    ArtifactResponse,
    ArtifactUploadResponse,
)
from settings.artifact import ArtifactSettings
from usecases.audit import AuditEvent, AuditUsecase

logger = logging.getLogger(__name__)

_GC_BATCH_SIZE = 100
_MIN_SIGNED_URL_LIFETIME = timedelta(seconds=1)


class ArtifactUsecase:
    """Upload, list, sign, delete, and expire tenant-owned artifacts."""

    def __init__(self, store: ArtifactStore, settings: ArtifactSettings) -> None:
        """Initialize storage and durable metadata dependencies."""
        self._store = store
        self._settings = settings
        self._repository = ArtifactRepository()
        self._audit_usecase = AuditUsecase()

    async def upload(
        self,
        session: AsyncSession,
        user_id: int,
        filename: str | None,
        mime_type: str | None,
        content: bytes,
    ) -> ArtifactUploadResponse:
        """Store immutable bytes or return the existing tenant duplicate."""
        if not content:
            raise EmptyArtifactError
        if len(content) > self._settings.max_upload_bytes:
            raise ArtifactTooLargeError

        # Serialize quota/dedup decisions for one owner. Auth already proves the
        # user exists; locking also prevents concurrent uploads exceeding quota.
        await session.execute(select(User).where(User.id == user_id).with_for_update())

        checksum = sha256(content).hexdigest()
        expires_at = self._expires_at()
        existing = await self._repository.get_by(
            session=session, user_id=user_id, checksum=checksum
        )
        if existing is not None:
            existing = await self._repository.update_by(
                session=session,
                id=existing.id,
                user_id=user_id,
                data={"expires_at": expires_at},
            )
            await session.commit()
            if existing is None:
                raise ArtifactNotFoundError
            return ArtifactUploadResponse(
                artifact=ArtifactResponse.model_validate(existing),
                deduplicated=True,
            )

        retained_bytes = await self._repository.sum_size(
            session=session, user_id=user_id, now=datetime.now(tz=UTC)
        )
        if (
            self._settings.max_user_bytes > 0
            and retained_bytes + len(content) > self._settings.max_user_bytes
        ):
            raise ArtifactQuotaExceededError

        safe_filename = self._safe_filename(filename)
        safe_mime_type = self._safe_mime_type(mime_type)
        object_key = f"users/{user_id}/sha256/{checksum}"
        try:
            await self._store.put(object_key, content, safe_mime_type)
        except ArtifactStorageError:
            await session.rollback()
            raise

        try:
            artifact = await self._repository.create(
                session=session,
                data={
                    "user_id": user_id,
                    "object_key": object_key,
                    "filename": safe_filename,
                    "mime_type": safe_mime_type,
                    "size": len(content),
                    "checksum": checksum,
                    "expires_at": expires_at,
                },
            )
            await self._audit_usecase.record(
                session=session,
                event=AuditEvent(
                    user_id=user_id,
                    action="artifact.create",
                    entity_type="artifact",
                    entity_id=artifact.id,
                    metadata={
                        "filename": safe_filename,
                        "mime_type": safe_mime_type,
                        "size": len(content),
                    },
                ),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            try:
                await self._store.delete(object_key)
            except ArtifactStorageError:
                logger.exception(
                    "Failed to remove orphan artifact object %s", object_key
                )
            raise

        return ArtifactUploadResponse(
            artifact=ArtifactResponse.model_validate(artifact), deduplicated=False
        )

    async def list_artifacts(
        self, session: AsyncSession, user_id: int, limit: int, offset: int
    ) -> list[ArtifactResponse]:
        """List active artifact metadata newest first."""
        artifacts = await self._repository.get_active(
            session=session,
            user_id=user_id,
            now=datetime.now(tz=UTC),
            limit=limit,
            offset=offset,
        )
        return [ArtifactResponse.model_validate(item) for item in artifacts]

    async def get_download(
        self, session: AsyncSession, user_id: int, artifact_id: int
    ) -> ArtifactDownloadResponse:
        """Return a short-lived signed URL for an owned active artifact."""
        artifact = await self._repository.get_by(
            session=session, id=artifact_id, user_id=user_id
        )
        if artifact is None:
            raise ArtifactNotFoundError
        now = datetime.now(tz=UTC)
        if artifact.expires_at is not None and artifact.expires_at <= now:
            raise ArtifactExpiredError
        lifetime = timedelta(seconds=self._settings.signed_url_expire_seconds)
        if artifact.expires_at is not None:
            retained_for = artifact.expires_at - now
            if retained_for < _MIN_SIGNED_URL_LIFETIME:
                raise ArtifactExpiredError
            lifetime = min(lifetime, retained_for)
        url = await self._store.signed_download_url(
            artifact.object_key, expires=lifetime
        )
        return ArtifactDownloadResponse(url=url, expires_at=now + lifetime)

    async def delete(
        self, session: AsyncSession, user_id: int, artifact_id: int
    ) -> None:
        """Delete one owned artifact from object storage and metadata."""
        artifact = await self._repository.get_by(
            session=session, id=artifact_id, user_id=user_id
        )
        if artifact is None:
            raise ArtifactNotFoundError
        await self._store.delete(artifact.object_key)
        await self._repository.delete_by(
            session=session, id=artifact_id, user_id=user_id
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="artifact.delete",
                entity_type="artifact",
                entity_id=artifact_id,
            ),
        )
        await session.commit()

    async def cleanup_expired(self, session: AsyncSession) -> int:
        """Delete one bounded batch of expired objects and metadata."""
        expired = await self._repository.get_expired(
            session=session, now=datetime.now(tz=UTC), limit=_GC_BATCH_SIZE
        )
        cleaned = 0
        for artifact in expired:
            try:
                await self._store.delete(artifact.object_key)
            except ArtifactStorageError:
                logger.exception(
                    "Failed to delete expired artifact object %s", artifact.object_key
                )
                continue
            await self._repository.delete_by(session=session, id=artifact.id)
            cleaned += 1
        await session.commit()
        return cleaned

    def _expires_at(self) -> datetime | None:
        """Calculate a retention deadline from current settings."""
        if self._settings.retention_days == 0:
            return None
        return datetime.now(tz=UTC) + timedelta(days=self._settings.retention_days)

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        """Strip paths/control bytes and bound an uploaded display filename."""
        cleaned = Path((filename or "upload").replace("\x00", "")).name.strip()
        return (cleaned or "upload")[:255]

    @staticmethod
    def _safe_mime_type(mime_type: str | None) -> str:
        """Normalize a bounded declared MIME type."""
        cleaned = (mime_type or "application/octet-stream").strip().lower()
        return (cleaned or "application/octet-stream")[:255]
