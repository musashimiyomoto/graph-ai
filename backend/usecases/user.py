"""User use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from repositories import UserRepository


class UserUsecase:
    """User business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._user_repository = UserRepository()

    async def delete_by(self, session: AsyncSession, user_id: int) -> None:
        """Delete a user by id.

        Args:
            session: The session.
            user_id: The user id.

        Raises:
            UserNotFoundError: If the user is not found.

        """
        await self._user_repository.delete_by(session=session, id=user_id)
