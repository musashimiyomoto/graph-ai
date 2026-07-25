"""Durable conversation business logic."""

import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation
from db.repositories import ConversationRepository
from enums import ExecutionSource
from schemas import TriggerConversation, TriggerEvent


def _external_thread(conversation: TriggerConversation) -> str:
    """Build a stable provider thread identity without cross-channel linking."""
    material = (
        f"{len(conversation.id)}:{conversation.id}:{conversation.thread_id or ''}"
    ).encode()
    return hashlib.md5(material, usedforsecurity=False).hexdigest()


class ConversationUsecase:
    """Resolve normalized trigger events to durable conversation records."""

    def __init__(self) -> None:
        """Initialize repositories."""
        self._repository = ConversationRepository()

    async def resolve_trigger(
        self,
        *,
        session: AsyncSession,
        owner_id: int,
        workflow_id: int,
        event: TriggerEvent,
    ) -> Conversation | None:
        """Find or create the workflow/channel thread for one trigger event."""
        if event.conversation is None:
            return None
        external_thread = _external_thread(event.conversation)
        lock_material = (
            f"conversation:{workflow_id}:{event.channel.value}:{external_thread}"
        ).encode()
        lock_key = int.from_bytes(
            hashlib.sha256(lock_material).digest()[:8],
            byteorder="big",
            signed=True,
        )
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))

        conversation = await self._repository.get_for_update(
            session=session,
            workflow_id=workflow_id,
            channel=event.channel,
            external_thread=external_thread,
        )
        actor = event.sender
        values = {
            "actor_id": actor.id if actor else None,
            "actor_display_name": actor.display_name if actor else None,
            "actor_address": actor.address if actor else None,
            "locale": event.locale,
            "last_event_at": event.occurred_at,
        }
        if conversation is None:
            return await self._repository.create(
                session=session,
                data={
                    "owner_id": owner_id,
                    "workflow_id": workflow_id,
                    "channel": event.channel,
                    "external_thread": external_thread,
                    "external_conversation_id": event.conversation.id,
                    "external_thread_id": event.conversation.thread_id,
                    **values,
                },
            )
        updated = await self._repository.update_by(
            session=session,
            data=values,
            id=conversation.id,
        )
        if updated is None:
            message = "Locked conversation disappeared during update"
            raise RuntimeError(message)
        return updated

    async def get_public_session(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        public_id: str,
    ) -> Conversation | None:
        """Resolve an opaque web-chat session inside one workflow."""
        return await self._repository.get_by(
            session=session,
            workflow_id=workflow_id,
            channel=ExecutionSource.WEB_CHAT,
            public_id=public_id,
        )
