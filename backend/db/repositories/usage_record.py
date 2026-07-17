"""Repository for per-tenant usage records."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UsageRecord
from db.repositories.base import BaseRepository


class UsageRecordRepository(BaseRepository[UsageRecord]):
    """Repository for UsageRecord model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the UsageRecord model."""
        super().__init__(model=UsageRecord)

    async def increment(
        self,
        session: AsyncSession,
        user_id: int,
        period_start: date,
        *,
        executions_delta: int,
        tokens_delta: int,
    ) -> UsageRecord:
        """Atomically add to a user's usage for a window, creating the row if new.

        Uses ``INSERT ... ON CONFLICT DO UPDATE`` so concurrent finalizing
        executions can't lose an increment to a read-modify-write race. Flushes
        but does not commit — the caller owns the transaction.

        Args:
            session: The async session.
            user_id: The tenant whose usage to increment.
            period_start: The usage window (UTC calendar day).
            executions_delta: Executions to add.
            tokens_delta: Tokens to add.

        Returns:
            The upserted usage record.

        """
        statement = (
            insert(UsageRecord)
            .values(
                user_id=user_id,
                period_start=period_start,
                executions_count=executions_delta,
                total_tokens=tokens_delta,
            )
            .on_conflict_do_update(
                constraint="uq_usage_records_user_period",
                set_={
                    "executions_count": UsageRecord.executions_count + executions_delta,
                    "total_tokens": UsageRecord.total_tokens + tokens_delta,
                },
            )
            .returning(UsageRecord)
        )
        result = await session.execute(statement)
        await session.flush()
        return result.scalar_one()

    async def get_for_period(
        self, session: AsyncSession, user_id: int, period_start: date
    ) -> UsageRecord | None:
        """Return a user's usage row for a window, or None if none exists yet.

        Args:
            session: The async session.
            user_id: The tenant.
            period_start: The usage window (UTC calendar day).

        Returns:
            The usage record, or None when the user has no usage in the window.

        """
        statement = select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.period_start == period_start,
        )
        return (await session.execute(statement)).scalar_one_or_none()
