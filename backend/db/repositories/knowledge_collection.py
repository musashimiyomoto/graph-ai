"""Repository for tenant knowledge collections."""

from db.models import KnowledgeCollection
from db.repositories.base import BaseRepository


class KnowledgeCollectionRepository(BaseRepository[KnowledgeCollection]):
    """Database access for logical-to-physical collection mappings."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=KnowledgeCollection)
