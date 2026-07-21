"""Artifact model factory."""

from datetime import UTC, datetime, timedelta

from factory.declarations import LazyAttribute, LazyFunction

from db.models.artifact import Artifact
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class ArtifactFactory(AsyncSQLAlchemyModelFactory):
    """Factory for tenant-owned artifact metadata."""

    class Meta:
        """Factory metadata."""

        model = Artifact

    user_id = None
    object_key = LazyAttribute(
        lambda obj: f"users/{obj.user_id}/sha256/{fake.sha256()}"
    )
    filename = LazyFunction(fake.file_name)
    mime_type = "application/octet-stream"
    size = 128
    checksum = LazyFunction(fake.sha256)
    expires_at = LazyFunction(lambda: datetime.now(tz=UTC) + timedelta(days=30))
