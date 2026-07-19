"""Repository for users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the User model."""
        super().__init__(model=User)

    async def get_by_for_update(
        self,
        session: AsyncSession,
        **filters: object,
    ) -> User | None:
        """Lock and return one user matching the supplied equality filters."""
        result = await session.execute(
            select(User).filter_by(**filters).with_for_update()
        )
        return result.scalar_one_or_none()
