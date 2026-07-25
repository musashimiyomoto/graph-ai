"""Repository for durable conversations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation
from db.repositories.base import BaseRepository
from enums import ExecutionSource


class ConversationRepository(BaseRepository[Conversation]):
    """Data access for workflow/channel conversation records."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=Conversation)

    async def get_for_update(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        channel: ExecutionSource,
        external_thread: str,
    ) -> Conversation | None:
        """Lock a conversation identity while it is created or refreshed."""
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.workflow_id == workflow_id,
                Conversation.channel == channel,
                Conversation.external_thread == external_thread,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
