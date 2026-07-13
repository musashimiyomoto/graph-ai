"""Repository for node schedules."""

from db.models import NodeSchedule
from db.repositories.base import BaseRepository


class NodeScheduleRepository(BaseRepository[NodeSchedule]):
    """Repository for NodeSchedule model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the NodeSchedule model."""
        super().__init__(model=NodeSchedule)
