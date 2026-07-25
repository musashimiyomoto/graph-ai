"""Email receive, acknowledge, and delivery adapter."""

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
from credentials import connection_secret
from db.models import EmailAccount
from db.repositories import (
    ConnectionRepository,
    EmailAccountRepository,
    NodeRepository,
    WorkflowRepository,
)
from enums import ExecutionSource, InputNodeFormat, NodeType, PortType
from exceptions import EmailConnectionError
from integrations.email import (
    EmailConnectionConfig,
    InboundEmail,
    fetch_messages,
    send_email,
)
from schemas import (
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _EmailCheckpoint:
    """Highest IMAP UID consumed for one account."""

    account_id: int
    last_uid: int


class EmailChannelAdapter:
    """Normalize IMAP messages and deliver completed results through SMTP."""

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Poll enabled accounts and normalize messages for matching Input nodes."""
        account_repository = EmailAccountRepository()
        node_repository = NodeRepository()
        workflow_repository = WorkflowRepository()
        accounts = await account_repository.get_all(
            session=context.session, enabled=True
        )
        input_nodes = await node_repository.get_all(
            session=context.session, type=NodeType.INPUT
        )
        batches: list[ChannelReceiveBatch] = []

        for account in accounts:
            triggered_nodes = [
                node
                for node in input_nodes
                if node.data.get("format") == InputNodeFormat.EMAIL.value
                and node.data.get("email_account_id") == account.id
            ]
            if not triggered_nodes:
                continue
            connection = await ConnectionRepository().get_by(
                session=context.session,
                id=account.connection_id,
                user_id=account.user_id,
            )
            password = connection_secret(connection) if connection is not None else None
            if password is None:
                logger.error(
                    "Email account %s has no credential connection", account.id
                )
                continue
            try:
                messages = await fetch_messages(
                    config=_connection_config(account, password),
                    last_uid=account.last_uid,
                )
            except EmailConnectionError:
                logger.exception("Failed to poll email account %s", account.id)
                continue

            events: list[ChannelInboundEvent] = []
            for node in triggered_nodes:
                workflow = await workflow_repository.get_by(
                    session=context.session, id=node.workflow_id
                )
                if workflow is None or workflow.owner_id != account.user_id:
                    continue
                events.extend(
                    ChannelInboundEvent(
                        workflow_id=node.workflow_id,
                        user_id=workflow.owner_id,
                        input_value=_input_value(message),
                        event=_trigger_event(account.id, message),
                    )
                    for message in messages
                    if message.sender
                )

            checkpoint = (
                _EmailCheckpoint(
                    account_id=account.id,
                    last_uid=max(message.uid for message in messages),
                )
                if messages
                else None
            )
            if events or checkpoint is not None:
                batches.append(
                    ChannelReceiveBatch(events=tuple(events), checkpoint=checkpoint)
                )

        return tuple(batches)

    async def acknowledge(self, context: ChannelAcknowledgeContext) -> None:
        """Advance an account's durable IMAP UID cursor."""
        if not isinstance(context.checkpoint, _EmailCheckpoint):
            message = "Email acknowledgement requires an email checkpoint"
            raise TypeError(message)
        await EmailAccountRepository().update_by(
            session=context.session,
            data={"last_uid": context.checkpoint.last_uid},
            id=context.checkpoint.account_id,
        )

    async def deliver(self, context: ChannelDeliveryContext) -> None:
        """Send a finished execution through its configured SMTP account."""
        workflow = await WorkflowRepository().get_by(
            session=context.session, id=context.execution.workflow_id
        )
        account_id = context.output_node.data.get("email_account_id")
        if workflow is None or not isinstance(account_id, int):
            return
        account = await EmailAccountRepository().get_by(
            session=context.session, id=account_id, user_id=workflow.owner_id
        )
        if account is None:
            return

        configured_recipient = context.output_node.data.get("email_to")
        recipient = (
            configured_recipient.strip()
            if isinstance(configured_recipient, str) and configured_recipient.strip()
            else _event_sender_address(context.execution.trigger_event)
        )
        text = delivery_text(context.execution)
        if not recipient or text is None:
            return
        connection = await ConnectionRepository().get_by(
            session=context.session,
            id=account.connection_id,
            user_id=account.user_id,
        )
        password = connection_secret(connection) if connection is not None else None
        if password is None:
            return
        await send_email(
            config=_connection_config(account, password),
            recipient=recipient,
            subject=_reply_subject(
                context.output_node.data.get("email_subject"),
                _event_subject(context.execution.trigger_event),
            ),
            text=text,
        )


def _connection_config(account: EmailAccount, password: str) -> EmailConnectionConfig:
    """Build decrypted integration configuration for an email account."""
    return EmailConnectionConfig(
        email_address=account.email_address,
        username=account.username,
        password=password,
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_use_ssl=account.imap_use_ssl,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_use_tls=account.smtp_use_tls,
        smtp_use_ssl=account.smtp_use_ssl,
    )


def _input_value(message: InboundEmail) -> str:
    """Compose subject and body into the engine's text input contract."""
    value = (
        f"Subject: {message.subject}\n\n{message.body}"
        if message.subject
        else message.body
    )
    return value[:50_000]


def _trigger_event(account_id: int, message: InboundEmail) -> TriggerEvent:
    """Build the canonical event for one inbound email."""
    input_value = _input_value(message)
    return TriggerEvent(
        channel=ExecutionSource.EMAIL,
        external_event_id=f"account:{account_id}:uid:{message.uid}",
        sender=TriggerActor(id=message.sender, address=message.sender),
        conversation=TriggerConversation(
            id=(
                message.thread_id
                or message.message_id
                or f"account:{account_id}:uid:{message.uid}"
            )
        ),
        locale=message.locale,
        message=NodeValuePayload(kind=PortType.TEXT, value=input_value),
        occurred_at=message.sent_at or datetime.now(tz=UTC),
        metadata={
            "account_id": account_id,
            "message_id": message.message_id,
            "subject": message.subject,
        },
    )


def _event_sender_address(trigger_event: dict[str, Any]) -> str | None:
    """Return the best reply address from a canonical trigger event."""
    sender = trigger_event.get("sender")
    if not isinstance(sender, dict):
        return None
    for field in ("address", "id"):
        value = sender.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _event_subject(trigger_event: dict[str, Any]) -> str | None:
    """Return the incoming subject from a canonical trigger event."""
    metadata = trigger_event.get("metadata")
    if not isinstance(metadata, dict):
        return None
    subject = metadata.get("subject")
    return subject if isinstance(subject, str) else None


def _reply_subject(configured: object, triggered: str | None) -> str:
    """Resolve a fixed subject or derive a conventional reply subject."""
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    if triggered:
        return triggered if triggered.lower().startswith("re:") else f"Re: {triggered}"
    return "Workflow result"


EMAIL_ADAPTER = EmailChannelAdapter()
