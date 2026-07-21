"""Tenant-scoped artifact API and lifecycle tests."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from api.dependencies import artifact as artifact_dependency
from db.repositories import ArtifactRepository
from main import app
from settings import artifact_settings
from tests.factories import ArtifactFactory
from tests.test_api.base import BaseTestCase
from usecases import ArtifactUsecase


class _FakeArtifactStore:
    """In-memory object store with deterministic signed URLs."""

    def __init__(self) -> None:
        """Initialize object and deletion tracking."""
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []
        self.signed_lifetimes: list[timedelta] = []

    async def ensure_bucket(self) -> None:
        """No-op for the in-memory bucket."""

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        """Store immutable bytes in memory."""
        self.objects[key] = (content, mime_type)

    async def delete(self, key: str) -> None:
        """Delete an object idempotently."""
        self.objects.pop(key, None)
        self.deleted.append(key)

    async def signed_download_url(self, key: str, expires: timedelta) -> str:
        """Return a recognizable fake URL."""
        self.signed_lifetimes.append(expires)
        return f"https://artifacts.example.test/{key}?signed=true"


class TestArtifactApi(BaseTestCase):
    """Artifact upload, deduplication, ownership, signing, and deletion."""

    url = "/artifacts"
    store: _FakeArtifactStore
    usecase: ArtifactUsecase

    @pytest.fixture(autouse=True)
    def override_artifact_usecase(self) -> None:
        """Inject a fresh in-memory store into each API test."""
        self.store = _FakeArtifactStore()
        settings = artifact_settings.model_copy(
            update={
                "max_upload_bytes": 32,
                "max_user_bytes": 64,
                "retention_days": 30,
                "signed_url_expire_seconds": 60,
            }
        )
        self.usecase = ArtifactUsecase(store=self.store, settings=settings)
        app.dependency_overrides[artifact_dependency.get_artifact_usecase] = lambda: (
            self.usecase
        )

    async def test_upload_deduplicates_and_returns_signed_download(self) -> None:
        """Identical tenant bytes reuse one object and remain downloadable."""
        _, headers = await self.create_user_and_get_token()
        first = await self.client.post(
            self.url,
            files={"file": ("note.txt", b"same content", "text/plain")},
            headers=headers,
        )
        if first.status_code != HTTPStatus.CREATED:
            pytest.fail(f"Unexpected upload status: {first.status_code}")
        first_data = first.json()
        if first_data["deduplicated"]:
            pytest.fail("First upload cannot be a duplicate")

        second = await self.client.post(
            self.url,
            files={"file": ("copy.txt", b"same content", "text/plain")},
            headers=headers,
        )
        second_data = second.json()
        if not second_data["deduplicated"]:
            pytest.fail("Second identical upload should be deduplicated")
        if second_data["artifact"]["id"] != first_data["artifact"]["id"]:
            pytest.fail("Deduplication returned a different artifact row")
        if len(self.store.objects) != 1:
            pytest.fail("Deduplication stored the bytes more than once")

        artifact_id = first_data["artifact"]["id"]
        download = await self.client.get(
            f"{self.url}/{artifact_id}/download", headers=headers
        )
        payload = await self.assert_response_dict(response=download)
        if "signed=true" not in payload["url"]:
            pytest.fail("Download endpoint did not return a signed URL")

    async def test_download_lifetime_is_capped_by_retention(self) -> None:
        """A signed URL cannot remain valid after artifact retention expires."""
        owner, headers = await self.create_user_and_get_token()
        retained_for = timedelta(seconds=5)
        artifact = await ArtifactFactory.create_async(
            session=self.session,
            user_id=owner["id"],
            expires_at=datetime.now(tz=UTC) + retained_for,
        )

        response = await self.client.get(
            f"{self.url}/{artifact.id}/download", headers=headers
        )

        await self.assert_response_dict(response=response)
        if len(self.store.signed_lifetimes) != 1:
            pytest.fail("Expected exactly one storage signing call")
        if self.store.signed_lifetimes[0] > retained_for:
            pytest.fail("Signed URL outlived the artifact retention deadline")

    async def test_list_and_delete_are_owner_scoped(self) -> None:
        """One user cannot see, sign, or delete another user's artifact."""
        owner, owner_headers = await self.create_user_and_get_token()
        _, stranger_headers = await self.create_user_and_get_token()
        artifact = await ArtifactFactory.create_async(
            session=self.session,
            user_id=owner["id"],
            object_key=f"users/{owner['id']}/sha256/owned",
        )
        self.store.objects[artifact.object_key] = (b"owned", artifact.mime_type)

        listed = await self.client.get(self.url, headers=owner_headers)
        data = await self.assert_response_list(response=listed)
        if [item["id"] for item in data] != [artifact.id]:
            pytest.fail("Owner artifact list is incorrect")

        stranger_download = await self.client.get(
            f"{self.url}/{artifact.id}/download", headers=stranger_headers
        )
        if stranger_download.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Foreign artifact download should look not-found")
        stranger_delete = await self.client.delete(
            f"{self.url}/{artifact.id}", headers=stranger_headers
        )
        if stranger_delete.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Foreign artifact deletion should look not-found")

        deleted = await self.client.delete(
            f"{self.url}/{artifact.id}", headers=owner_headers
        )
        await self.assert_response_ok(response=deleted)
        if artifact.object_key not in self.store.deleted:
            pytest.fail("Owned object was not removed from storage")

    async def test_upload_enforces_size_and_total_quota(self) -> None:
        """Per-file and retained-byte limits reject uploads before storage."""
        _, headers = await self.create_user_and_get_token()
        too_large = await self.client.post(
            self.url,
            files={"file": ("large.bin", b"x" * 33, "application/octet-stream")},
            headers=headers,
        )
        if too_large.status_code != HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
            pytest.fail("Oversized artifact was accepted")

        for name, content in (("one.bin", b"a" * 32), ("two.bin", b"b" * 32)):
            response = await self.client.post(
                self.url,
                files={"file": (name, content, "application/octet-stream")},
                headers=headers,
            )
            if response.status_code != HTTPStatus.CREATED:
                pytest.fail("Upload within total quota was rejected")
        over_quota = await self.client.post(
            self.url,
            files={"file": ("three.bin", b"c", "application/octet-stream")},
            headers=headers,
        )
        if over_quota.status_code != HTTPStatus.TOO_MANY_REQUESTS:
            pytest.fail("Artifact total-byte quota was not enforced")

    async def test_expired_artifact_is_gone_and_gc_removes_it(self) -> None:
        """Expired metadata cannot be signed and cleanup removes bytes and row."""
        owner, headers = await self.create_user_and_get_token()
        artifact = await ArtifactFactory.create_async(
            session=self.session,
            user_id=owner["id"],
            object_key=f"users/{owner['id']}/sha256/expired",
            expires_at=datetime.now(tz=UTC) - timedelta(seconds=1),
        )
        self.store.objects[artifact.object_key] = (b"old", artifact.mime_type)
        response = await self.client.get(
            f"{self.url}/{artifact.id}/download", headers=headers
        )
        if response.status_code != HTTPStatus.GONE:
            pytest.fail("Expired artifact should return 410")

        cleaned = await self.usecase.cleanup_expired(session=self.session)
        if cleaned != 1:
            pytest.fail("Expired artifact was not cleaned")
        if (
            await ArtifactRepository().get_by(session=self.session, id=artifact.id)
            is not None
        ):
            pytest.fail("Expired artifact metadata remains after cleanup")
