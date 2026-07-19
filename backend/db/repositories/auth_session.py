"""Repository for persistent authentication sessions."""

from datetime import datetime

from sqlalchemy import select, update
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

    async def revoke_all_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        revoked_at: datetime,
    ) -> None:
        """Revoke every active session after a credential change."""
        await session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        await session.flush()
