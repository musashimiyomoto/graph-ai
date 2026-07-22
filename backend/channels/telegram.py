"""Telegram receive, acknowledge, and delivery adapter."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from channels.base import (
    ChannelAcknowledgeContext,
    ChannelDeliveryContext,
    ChannelInboundEvent,
    ChannelReceiveBatch,
    ChannelReceiveContext,
    delivery_text,
)
from db.repositories import (
    NodeRepository,
    TelegramBotRepository,
    WorkflowRepository,
)
from enums import ExecutionSource, InputNodeFormat, NodeType, PortType
from exceptions import TelegramAPIError
from integrations.telegram import get_updates, send_message
from schemas import (
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
)
from utils.encryption import decrypt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TelegramInboundMessage:
    """Normalized Telegram message retained without the raw provider payload."""

    update_id: int
    chat_id: int
    text: str
    occurred_at: datetime
    message_id: int | None = None
    thread_id: int | None = None
    sender_id: int | None = None
    sender_name: str | None = None
    sender_username: str | None = None
    locale: str | None = None


@dataclass(frozen=True)
class _TelegramCheckpoint:
    """Highest provider update consumed for one bot."""

    bot_id: int
    update_id: int


class TelegramChannelAdapter:
    """Normalize Telegram updates and send completed workflow replies."""

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Poll configured bots and normalize updates for their Input nodes."""
        bot_repository = TelegramBotRepository()
        node_repository = NodeRepository()
        workflow_repository = WorkflowRepository()
        bots = await bot_repository.get_all(session=context.session, enabled=True)
        input_nodes = await node_repository.get_all(
            session=context.session, type=NodeType.INPUT
        )
        batches: list[ChannelReceiveBatch] = []

        for bot in bots:
            triggered_nodes = [
                node
                for node in input_nodes
                if node.data.get("format") == InputNodeFormat.TELEGRAM.value
                and node.data.get("telegram_bot_id") == bot.id
            ]
            if not triggered_nodes:
                continue
            try:
                updates = await get_updates(
                    bot_token=decrypt(bot.bot_token), offset=bot.last_update_id + 1
                )
            except TelegramAPIError:
                logger.exception("Failed to poll Telegram updates for bot %s", bot.id)
                continue

            max_update_id = bot.last_update_id
            messages: list[_TelegramInboundMessage] = []
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    max_update_id = max(max_update_id, update_id)
                message = _extract_message(update)
                if message is not None:
                    messages.append(message)

            events: list[ChannelInboundEvent] = []
            for node in triggered_nodes:
                workflow = await workflow_repository.get_by(
                    session=context.session, id=node.workflow_id
                )
                if workflow is None or workflow.owner_id != bot.user_id:
                    continue
                events.extend(
                    ChannelInboundEvent(
                        workflow_id=node.workflow_id,
                        user_id=workflow.owner_id,
                        input_value=message.text,
                        event=_trigger_event(bot.id, message),
                    )
                    for message in messages
                )

            checkpoint = (
                _TelegramCheckpoint(bot_id=bot.id, update_id=max_update_id)
                if max_update_id != bot.last_update_id
                else None
            )
            if events or checkpoint is not None:
                batches.append(
                    ChannelReceiveBatch(events=tuple(events), checkpoint=checkpoint)
                )

        return tuple(batches)

    async def acknowledge(self, context: ChannelAcknowledgeContext) -> None:
        """Advance a bot's durable Telegram update offset."""
        if not isinstance(context.checkpoint, _TelegramCheckpoint):
            message = "Telegram acknowledgement requires a Telegram checkpoint"
            raise TypeError(message)
        await TelegramBotRepository().update_by(
            session=context.session,
            data={"last_update_id": context.checkpoint.update_id},
            id=context.checkpoint.bot_id,
        )

    async def deliver(self, context: ChannelDeliveryContext) -> None:
        """Send a finished execution through its configured Telegram bot."""
        node_data = context.output_node.data
        bot_id = node_data.get("telegram_bot_id")
        if not isinstance(bot_id, int):
            return
        bot = await TelegramBotRepository().get_by(session=context.session, id=bot_id)
        chat_id = _reply_chat_id(node_data, context.execution.trigger_event)
        text = delivery_text(context.execution)
        if bot is None or chat_id is None or text is None:
            return
        await send_message(
            bot_token=decrypt(bot.bot_token),
            chat_id=chat_id,
            text=text,
        )


def _trigger_event(bot_id: int, message: _TelegramInboundMessage) -> TriggerEvent:
    """Build the canonical event for one Telegram update."""
    return TriggerEvent(
        channel=ExecutionSource.TELEGRAM,
        external_event_id=f"bot:{bot_id}:update:{message.update_id}",
        sender=(
            TriggerActor(
                id=str(message.sender_id),
                display_name=message.sender_name,
                address=(
                    f"@{message.sender_username}" if message.sender_username else None
                ),
            )
            if message.sender_id is not None
            else None
        ),
        conversation=TriggerConversation(
            id=str(message.chat_id),
            thread_id=(
                str(message.thread_id) if message.thread_id is not None else None
            ),
        ),
        locale=message.locale,
        message=NodeValuePayload(kind=PortType.TEXT, value=message.text),
        occurred_at=message.occurred_at,
        metadata={"bot_id": bot_id, "message_id": message.message_id},
    )


def _reply_chat_id(
    node_data: dict[str, Any], trigger_event: dict[str, Any]
) -> int | None:
    """Pick a pinned chat ID or the triggering conversation ID."""
    pinned_chat_id = node_data.get("telegram_chat_id")
    if isinstance(pinned_chat_id, int):
        return pinned_chat_id
    conversation = trigger_event.get("conversation")
    if not isinstance(conversation, dict):
        return None
    conversation_id = conversation.get("id")
    if not isinstance(conversation_id, str):
        return None
    try:
        return int(conversation_id)
    except ValueError:
        return None


def _extract_message(update: dict[str, Any]) -> _TelegramInboundMessage | None:
    """Normalize one Telegram update without retaining the provider payload."""
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    update_id = update.get("update_id")
    text = message.get("text")
    chat = message.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if (
        not isinstance(update_id, int)
        or not isinstance(text, str)
        or not text
        or not isinstance(chat_id, int)
    ):
        return None

    sender = message.get("from")
    sender_id = sender.get("id") if isinstance(sender, dict) else None
    first_name = sender.get("first_name") if isinstance(sender, dict) else None
    last_name = sender.get("last_name") if isinstance(sender, dict) else None
    sender_name = " ".join(
        part for part in (first_name, last_name) if isinstance(part, str) and part
    )
    timestamp = message.get("date")
    occurred_at = (
        datetime.fromtimestamp(timestamp, tz=UTC)
        if isinstance(timestamp, int | float)
        else datetime.now(tz=UTC)
    )
    message_id = message.get("message_id")
    thread_id = message.get("message_thread_id")
    username = sender.get("username") if isinstance(sender, dict) else None
    locale = sender.get("language_code") if isinstance(sender, dict) else None
    return _TelegramInboundMessage(
        update_id=update_id,
        chat_id=chat_id,
        text=text,
        occurred_at=occurred_at,
        message_id=message_id if isinstance(message_id, int) else None,
        thread_id=thread_id if isinstance(thread_id, int) else None,
        sender_id=sender_id if isinstance(sender_id, int) else None,
        sender_name=sender_name or None,
        sender_username=username if isinstance(username, str) else None,
        locale=locale if isinstance(locale, str) else None,
    )


TELEGRAM_ADAPTER = TelegramChannelAdapter()
