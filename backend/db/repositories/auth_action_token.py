"""Repository for one-time authentication action tokens."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuthActionToken
from db.repositories.base import BaseRepository


class AuthActionTokenRepository(BaseRepository[AuthActionToken]):
    """Authentication action token repository."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=AuthActionToken)

    async def get_by_hash_for_update(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> AuthActionToken | None:
        """Lock and return the row matching an opaque token hash."""
        result = await session.execute(
            select(AuthActionToken)
            .where(AuthActionToken.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()
