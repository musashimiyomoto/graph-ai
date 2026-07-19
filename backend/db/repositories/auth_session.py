"""Repository for persistent authentication sessions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuthSession
from db.repositories.base import BaseRepository


class AuthSessionRepository(BaseRepository[AuthSession]):
    """Refresh-session repository."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=AuthSession)

    async def get_by_hash_for_update(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> AuthSession | None:
        """Lock and return the session matching a refresh-token hash."""
        result = await session.execute(
            select(AuthSession)
            .where(AuthSession.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()
