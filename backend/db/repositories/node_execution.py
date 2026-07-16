"""Repository for node executions."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NodeExecution
from db.repositories.base import BaseRepository


class NodeExecutionRepository(BaseRepository[NodeExecution]):
    """Repository for NodeExecution model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the NodeExecution model."""
        super().__init__(model=NodeExecution)

    async def sum_tokens(
        self, session: AsyncSession, execution_id: int
    ) -> tuple[int, int, int]:
        """Sum token counts across every node result of an execution.

        Args:
            session: The async session.
            execution_id: The execution whose node results to sum.

        Returns:
            A ``(prompt_tokens, completion_tokens, total_tokens)`` tuple; each
            component is 0 when no node in the run reported that count (e.g. a
            run with no LLM nodes).

        """
        statement = select(
            func.coalesce(func.sum(NodeExecution.prompt_tokens), 0),
            func.coalesce(func.sum(NodeExecution.completion_tokens), 0),
            func.coalesce(func.sum(NodeExecution.total_tokens), 0),
        ).where(NodeExecution.execution_id == execution_id)
        row = (await session.execute(statement)).one()
        return int(row[0]), int(row[1]), int(row[2])
