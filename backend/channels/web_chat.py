"""Embedded web-chat receive adapter and workflow authorization."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from channels.base import (
    ChannelInboundEvent,
    ChannelReceiveBatch,
    ChannelReceiveContext,
)
from db.models import Workflow
from db.repositories import (
    ConversationRepository,
    NodeRepository,
    WorkflowRepository,
)
from enums import (
    ExecutionSource,
    InputNodeFormat,
    NodeType,
    OutputNodeFormat,
    PortType,
)
from exceptions import WebChatNotFoundError
from schemas import (
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
    WebChatMessage,
)
from utils.web_chat import parse_web_chat_token


@dataclass(frozen=True)
class WebChatReceivePayload:
    """Signed workflow token and one visitor message."""

    token: str
    message: WebChatMessage


class WebChatChannelAdapter:
    """Authorize embedded chat workflows and normalize visitor messages."""

    async def enabled_workflow(self, *, session: AsyncSession, token: str) -> Workflow:
        """Resolve a token and require matching web-chat Input and Output nodes."""
        workflow_id = parse_web_chat_token(token)
        if workflow_id is None:
            raise WebChatNotFoundError
        workflow = await WorkflowRepository().get_by(session=session, id=workflow_id)
        if workflow is None:
            raise WebChatNotFoundError

        node_repository = NodeRepository()
        input_node = await node_repository.get_by(
            session=session,
            workflow_id=workflow_id,
            type=NodeType.INPUT,
            parent_node_id=None,
        )
        output_node = await node_repository.get_by(
            session=session,
            workflow_id=workflow_id,
            type=NodeType.OUTPUT,
            parent_node_id=None,
        )
        if (
            input_node is None
            or input_node.data.get("format") != InputNodeFormat.WEB_CHAT.value
            or output_node is None
            or output_node.data.get("format") != OutputNodeFormat.WEB_CHAT.value
        ):
            raise WebChatNotFoundError
        return workflow

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Normalize one visitor message from the public chat widget."""
        if not isinstance(context.payload, WebChatReceivePayload):
            message = "Web chat receive requires a web-chat payload"
            raise TypeError(message)
        payload = context.payload
        workflow = await self.enabled_workflow(
            session=context.session, token=payload.token
        )
        message = payload.message
        external_thread, actor_id = await self._session_identity(
            session=context.session,
            workflow_id=workflow.id,
            message=message,
        )
        return (
            ChannelReceiveBatch(
                events=(
                    ChannelInboundEvent(
                        workflow_id=workflow.id,
                        user_id=workflow.owner_id,
                        input_value=message.value,
                        event=TriggerEvent(
                            channel=ExecutionSource.WEB_CHAT,
                            external_event_id=message.event_id,
                            sender=TriggerActor(id=actor_id),
                            conversation=TriggerConversation(id=external_thread),
                            locale=message.locale,
                            message=NodeValuePayload(
                                kind=PortType.TEXT,
                                value=message.value,
                            ),
                            occurred_at=datetime.now(tz=UTC),
                        ),
                    ),
                )
            ),
        )

    async def _session_identity(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        message: WebChatMessage,
    ) -> tuple[str, str]:
        """Resolve a server-issued session or seed a new opaque identity."""
        if message.session_id is not None:
            conversation = await ConversationRepository().get_by(
                session=session,
                workflow_id=workflow_id,
                channel=ExecutionSource.WEB_CHAT,
                public_id=message.session_id,
            )
            if conversation is None:
                raise WebChatNotFoundError
            return (
                conversation.external_conversation_id,
                conversation.actor_id or conversation.public_id,
            )
        seed = uuid4().hex
        return seed, seed


WEB_CHAT_ADAPTER = WebChatChannelAdapter()
