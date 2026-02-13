"""Repository for executions."""

from db.models import Execution
from db.repositories.base import BaseRepository


class ExecutionRepository(BaseRepository[Execution]):
    """Repository for Execution model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the Execution model."""
        super().__init__(model=Execution)
