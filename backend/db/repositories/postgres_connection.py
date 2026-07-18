"""Repository for saved PostgreSQL connections."""

from db.models import PostgresConnection
from db.repositories.base import BaseRepository


class PostgresConnectionRepository(BaseRepository[PostgresConnection]):
    """Repository for PostgreSQL connection operations."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=PostgresConnection)
