"""Repository for revisioned knowledge source metadata."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KnowledgeSource
from db.repositories.base import BaseRepository


class KnowledgeSourceRepository(BaseRepository[KnowledgeSource]):
    """Database access for source revisions and retention state."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=KnowledgeSource)

    async def list_active(
        self, *, session: AsyncSession, collection_id: int, now: datetime
    ) -> list[KnowledgeSource]:
        """List non-expired sources for one collection."""
        result = await session.execute(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.collection_id == collection_id,
                or_(
                    KnowledgeSource.expires_at.is_(None),
                    KnowledgeSource.expires_at > now,
                ),
            )
            .order_by(KnowledgeSource.source.asc())
        )
        return list(result.scalars().all())

    async def list_expired(
        self, *, session: AsyncSession, now: datetime, limit: int
    ) -> list[KnowledgeSource]:
        """Return a bounded oldest-first batch past its retention deadline."""
        result = await session.execute(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.expires_at.is_not(None),
                KnowledgeSource.expires_at <= now,
            )
            .order_by(KnowledgeSource.expires_at.asc(), KnowledgeSource.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
