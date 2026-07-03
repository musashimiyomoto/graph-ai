"""Repository for executions."""

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Execution
from db.repositories.base import BaseRepository
from enums import ExecutionStatus

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


class ExecutionRepository(BaseRepository[Execution]):
    """Repository for Execution model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the Execution model."""
        super().__init__(model=Execution)

    async def update_status_if(
        self,
        session: AsyncSession,
        execution_id: int,
        expected_status: ExecutionStatus,
        data: dict[str, Any],
    ) -> bool:
        """Atomically apply an update only if the row is in the expected status.

        A single ``UPDATE ... WHERE id = :id AND status = :expected`` acts as a
        compare-and-set, so the worker and the reaper cannot clobber each other's
        terminal writes.

        Args:
            session: The async session.
            execution_id: The execution to update.
            expected_status: The status the row must currently have.
            data: The columns to set (should include the new ``status``).

        Returns:
            True if the row was updated (this caller won the race), else False.

        """
        result = await session.execute(
            update(Execution)
            .where(
                Execution.id == execution_id,
                Execution.status == expected_status,
            )
            .values(**data)
        )
        await session.commit()
        return bool(cast("CursorResult[Any]", result).rowcount)
