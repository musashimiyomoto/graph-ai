"""Repository for workflow versions."""

from db.models import WorkflowVersion
from db.repositories.base import BaseRepository


class WorkflowVersionRepository(BaseRepository[WorkflowVersion]):
    """Repository for WorkflowVersion model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the WorkflowVersion model."""
        super().__init__(model=WorkflowVersion)
