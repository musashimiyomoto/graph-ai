"""Repository for email accounts."""

from db.models import EmailAccount
from db.repositories.base import BaseRepository


class EmailAccountRepository(BaseRepository[EmailAccount]):
    """Repository for EmailAccount model operations."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=EmailAccount)
