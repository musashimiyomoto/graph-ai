"""Repositories for typed durable state and its history."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import StateEntry, StateEntryHistory
from db.repositories.base import BaseRepository
from enums import StateScope


class StateEntryRepository(BaseRepository[StateEntry]):
    """Data access for current durable state values."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=StateEntry)

    async def get_for_update(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        scope: StateScope,
        scope_ref: str,
        key: str,
    ) -> StateEntry | None:
        """Lock one state key for compare-and-set mutation."""
        result = await session.execute(
            select(StateEntry)
            .where(
                StateEntry.workflow_id == workflow_id,
                StateEntry.scope == scope,
                StateEntry.scope_ref == scope_ref,
                StateEntry.key == key,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()


class StateEntryHistoryRepository(BaseRepository[StateEntryHistory]):
    """Data access for append-only durable state history."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=StateEntryHistory)
