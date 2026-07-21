"""S3-compatible artifact storage adapter tests."""

from datetime import timedelta
from io import BytesIO
from typing import TYPE_CHECKING, cast

import pytest

from artifacts import MinioArtifactStore
from exceptions import ArtifactStorageError
from settings.artifact import ArtifactSettings

if TYPE_CHECKING:
    from collections.abc import Callable

    from minio import Minio


class _FakeMinio:
    """Synchronous MinIO client double used behind the async adapter."""

    def __init__(self, endpoint: str, *, bucket_exists: bool = True) -> None:
        """Initialize call tracking for one endpoint."""
        self.endpoint = endpoint
        self.has_bucket = bucket_exists
        self.created_buckets: list[str] = []
        self.uploads: list[tuple[str, str, bytes, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.signed: list[tuple[str, str, timedelta]] = []
        self.failure: Exception | None = None

    def bucket_exists(self, bucket: str) -> bool:
        """Return configured bucket state or fail like a network client."""
        del bucket
        if self.failure is not None:
            raise self.failure
        return self.has_bucket

    def make_bucket(self, bucket: str) -> None:
        """Record bucket creation."""
        self.created_buckets.append(bucket)

    def put_object(
        self,
        bucket: str,
        key: str,
        stream: BytesIO,
        length: int,
        *,
        content_type: str,
    ) -> None:
        """Capture uploaded bytes and metadata."""
        self.uploads.append((bucket, key, stream.read(length), content_type))

    def remove_object(self, bucket: str, key: str) -> None:
        """Capture an idempotent deletion."""
        self.deleted.append((bucket, key))

    def presigned_get_object(self, bucket: str, key: str, *, expires: timedelta) -> str:
        """Capture signing and return an endpoint-specific URL."""
        self.signed.append((bucket, key, expires))
        return f"https://{self.endpoint}/{bucket}/{key}?signed=true"


class _ClientFactory:
    """Return separate clients for internal I/O and public URL signing."""

    def __init__(self, *, bucket_exists: bool = True) -> None:
        """Initialize created-client tracking."""
        self.bucket_exists = bucket_exists
        self.clients: list[_FakeMinio] = []

    def __call__(self, endpoint: str, **kwargs: object) -> _FakeMinio:
        """Create a fake client while accepting SDK credentials."""
        del kwargs
        client = _FakeMinio(endpoint, bucket_exists=self.bucket_exists)
        self.clients.append(client)
        return client


def _store(
    factory: _ClientFactory, *, public_endpoint: str = "files.example.test"
) -> MinioArtifactStore:
    """Build a store with deterministic test settings and clients."""
    settings = ArtifactSettings(
        endpoint="minio.internal:9000",
        public_endpoint=public_endpoint,
        bucket="test-artifacts",
    )
    client_factory = cast("Callable[..., Minio]", factory)
    return MinioArtifactStore(settings, client_factory=client_factory)


async def test_storage_creates_bucket_and_manages_objects() -> None:
    """The adapter delegates bucket, upload, and delete operations internally."""
    factory = _ClientFactory(bucket_exists=False)
    store = _store(factory)
    internal, public = factory.clients

    await store.ensure_bucket()
    await store.put("users/1/sha256/abc", b"payload", "text/plain")
    await store.delete("users/1/sha256/abc")

    if internal.created_buckets != ["test-artifacts"]:
        pytest.fail("Missing bucket was not created")
    if internal.uploads != [
        ("test-artifacts", "users/1/sha256/abc", b"payload", "text/plain")
    ]:
        pytest.fail("Artifact upload was delegated incorrectly")
    if internal.deleted != [("test-artifacts", "users/1/sha256/abc")]:
        pytest.fail("Artifact deletion was delegated incorrectly")
    if public.uploads or public.deleted:
        pytest.fail("Public signing client performed internal object I/O")


async def test_signed_url_uses_browser_reachable_endpoint() -> None:
    """Presigning uses the public client without making an internal request."""
    factory = _ClientFactory()
    store = _store(factory, public_endpoint="cdn.example.test")
    lifetime = timedelta(minutes=5)

    url = await store.signed_download_url("users/1/sha256/abc", lifetime)

    internal, public = factory.clients
    if not url.startswith("https://cdn.example.test/"):
        pytest.fail("Signed URL did not use the browser-reachable endpoint")
    if internal.signed:
        pytest.fail("Internal endpoint signed a browser URL")
    if public.signed != [("test-artifacts", "users/1/sha256/abc", lifetime)]:
        pytest.fail("Public signing call did not preserve key or lifetime")


async def test_network_failures_are_normalized() -> None:
    """Low-level client failures cross the adapter as one domain exception."""
    factory = _ClientFactory()
    store = _store(factory)
    factory.clients[0].failure = OSError("connection refused")

    with pytest.raises(ArtifactStorageError):
        await store.ensure_bucket()
