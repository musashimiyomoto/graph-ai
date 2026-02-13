"""Repository for users."""

from db.models import User
from db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the User model."""
        super().__init__(model=User)
