"""Repository for edges."""

from db.models import Edge
from db.repositories.base import BaseRepository


class EdgeRepository(BaseRepository[Edge]):
    """Repository for Edge model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the Edge model."""
        super().__init__(model=Edge)
