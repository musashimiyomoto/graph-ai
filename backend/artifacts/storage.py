"""Async facade over S3-compatible artifact object storage."""

from asyncio import to_thread
from collections.abc import Callable
from datetime import timedelta
from io import BytesIO
from typing import Protocol

from minio import Minio
from minio.error import MinioException
from urllib3.exceptions import HTTPError

from exceptions import ArtifactStorageError
from settings import artifact_settings
from settings.artifact import ArtifactSettings

_STORAGE_EXCEPTIONS = (MinioException, HTTPError, OSError)


class ArtifactStore(Protocol):
    """Object-storage operations required by the artifact use case."""

    async def ensure_bucket(self) -> None:
        """Create the configured bucket when it does not exist."""

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        """Store bytes at a tenant-scoped object key."""

    async def delete(self, key: str) -> None:
        """Delete an object if present."""

    async def signed_download_url(self, key: str, expires: timedelta) -> str:
        """Return a browser-reachable signed GET URL."""


class MinioArtifactStore:
    """S3-compatible artifact store implemented with the MinIO SDK."""

    def __init__(
        self,
        settings: ArtifactSettings,
        *,
        client_factory: Callable[..., Minio] = Minio,
    ) -> None:
        """Build internal and public-signing clients from settings."""
        self._settings = settings
        self._internal = client_factory(
            settings.endpoint,
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            secure=settings.secure,
        )
        self._public = client_factory(
            settings.public_endpoint,
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            secure=settings.public_secure,
        )

    async def ensure_bucket(self) -> None:
        """Create the artifact bucket once when it is missing."""
        try:
            exists = await to_thread(
                self._internal.bucket_exists,
                self._settings.bucket,
            )
            if not exists:
                await to_thread(self._internal.make_bucket, self._settings.bucket)
        except _STORAGE_EXCEPTIONS as exc:
            raise ArtifactStorageError from exc

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        """Upload one immutable content-addressed object."""
        stream = BytesIO(content)
        try:
            await to_thread(
                self._internal.put_object,
                self._settings.bucket,
                key,
                stream,
                len(content),
                content_type=mime_type,
            )
        except _STORAGE_EXCEPTIONS as exc:
            raise ArtifactStorageError from exc

    async def delete(self, key: str) -> None:
        """Delete one object; S3 deletion is idempotent for missing keys."""
        try:
            await to_thread(
                self._internal.remove_object,
                self._settings.bucket,
                key,
            )
        except _STORAGE_EXCEPTIONS as exc:
            raise ArtifactStorageError from exc

    async def signed_download_url(self, key: str, expires: timedelta) -> str:
        """Sign a GET URL using the endpoint reachable by the browser."""
        try:
            return await to_thread(
                self._public.presigned_get_object,
                self._settings.bucket,
                key,
                expires=expires,
            )
        except _STORAGE_EXCEPTIONS as exc:
            raise ArtifactStorageError from exc


artifact_store = MinioArtifactStore(artifact_settings)
