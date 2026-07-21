"""Repository for tenant-owned artifact metadata."""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Artifact
from db.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository[Artifact]):
    """Artifact metadata queries beyond generic CRUD."""

    def __init__(self) -> None:
        """Initialize the repository for Artifact rows."""
        super().__init__(model=Artifact)

    async def sum_size(self, session: AsyncSession, user_id: int, now: datetime) -> int:
        """Return total retained bytes owned by one user."""
        result = await session.execute(
            select(func.coalesce(func.sum(Artifact.size), 0)).where(
                Artifact.user_id == user_id,
                or_(Artifact.expires_at.is_(None), Artifact.expires_at > now),
            )
        )
        return int(result.scalar_one())

    async def get_active(
        self,
        session: AsyncSession,
        user_id: int,
        now: datetime,
        limit: int,
        offset: int,
    ) -> list[Artifact]:
        """List active artifacts for one owner, newest first."""
        result = await session.execute(
            select(Artifact)
            .where(
                Artifact.user_id == user_id,
                or_(Artifact.expires_at.is_(None), Artifact.expires_at > now),
            )
            .order_by(Artifact.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_expired(
        self, session: AsyncSession, now: datetime, limit: int
    ) -> list[Artifact]:
        """Return the oldest expired artifacts in a bounded cleanup batch."""
        result = await session.execute(
            select(Artifact)
            .where(Artifact.expires_at.is_not(None), Artifact.expires_at <= now)
            .order_by(Artifact.expires_at.asc(), Artifact.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
