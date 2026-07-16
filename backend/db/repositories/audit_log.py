"""Repository for audit log records."""

from db.models import AuditLog
from db.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for AuditLog model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the AuditLog model."""
        super().__init__(model=AuditLog)
