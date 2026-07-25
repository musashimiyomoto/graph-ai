"""Knowledge collection model factory."""

from uuid import uuid4

from factory.declarations import LazyFunction

from db.models import KnowledgeCollection
from tests.factories.base import AsyncSQLAlchemyModelFactory


class KnowledgeCollectionFactory(AsyncSQLAlchemyModelFactory):
    """Factory for owner-scoped logical collection mappings."""

    class Meta:
        """Factory meta configuration."""

        model = KnowledgeCollection

    owner_id = None
    name = LazyFunction(lambda: f"Collection {uuid4().hex[:8]}")
    physical_name = LazyFunction(lambda: f"tenant_test_{uuid4().hex}")
