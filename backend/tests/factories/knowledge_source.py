"""Knowledge source model factory."""

from datetime import UTC, datetime

from factory.declarations import LazyFunction

from db.models import KnowledgeSource
from tests.factories.base import AsyncSQLAlchemyModelFactory


class KnowledgeSourceFactory(AsyncSQLAlchemyModelFactory):
    """Factory for revisioned source metadata."""

    class Meta:
        """Factory meta configuration."""

        model = KnowledgeSource

    owner_id = None
    collection_id = None
    source = "document.txt"
    source_type = "upload"
    external_id = None
    revision = None
    content_hash = "0" * 64
    acl = LazyFunction(lambda: {"visibility": "private", "readers": []})
    source_metadata = LazyFunction(dict)
    chunk_count = 1
    expires_at = None
    last_synced_at = datetime.now(tz=UTC)
