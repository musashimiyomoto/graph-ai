"""Repository for nodes."""

from db.models import Node
from db.repositories.base import BaseRepository


class NodeRepository(BaseRepository[Node]):
    """Repository for Node model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the Node model."""
        super().__init__(model=Node)
