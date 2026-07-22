"""Signed public webhook receive and callback delivery adapter."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from channels.base import (
    ChannelDeliveryContext,
    ChannelInboundEvent,
    ChannelReceiveBatch,
    ChannelReceiveContext,
)
from db.repositories import NodeRepository, WorkflowRepository
from enums import ExecutionSource, InputNodeFormat, NodeType, PortType
from exceptions import ExecutionInputValidationError, WebhookNotFoundError
from integrations.webhook import send_webhook
from schemas import (
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
)
from utils.webhooks import parse_webhook_token

_MAX_INPUT_CHARS = 50_000
_MAX_EVENT_ID_CHARS = 255


@dataclass(frozen=True)
class WebhookInboundRequest:
    """Bounded body and normalized public webhook headers."""

    body: bytes
    content_type: str | None
    event_id: str | None
    sender_id: str | None
    conversation_id: str | None
    locale: str | None


@dataclass(frozen=True)
class WebhookReceivePayload:
    """Signed workflow token and its inbound request."""

    token: str
    request: WebhookInboundRequest


class WebhookChannelAdapter:
    """Normalize signed webhook requests and POST completed results."""

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Validate one push request and normalize its trigger event."""
        if not isinstance(context.payload, WebhookReceivePayload):
            message = "Webhook receive requires a webhook payload"
            raise TypeError(message)
        payload = context.payload
        workflow_id = parse_webhook_token(payload.token)
        if workflow_id is None:
            raise WebhookNotFoundError

        workflow = await WorkflowRepository().get_by(
            session=context.session, id=workflow_id
        )
        if workflow is None:
            raise WebhookNotFoundError
        input_node = await NodeRepository().get_by(
            session=context.session,
            workflow_id=workflow_id,
            type=NodeType.INPUT,
            parent_node_id=None,
        )
        if (
            input_node is None
            or input_node.data.get("format") != InputNodeFormat.WEBHOOK.value
        ):
            raise WebhookNotFoundError

        request = payload.request
        if not request.event_id or len(request.event_id) > _MAX_EVENT_ID_CHARS:
            message = "Webhook requests require an Idempotency-Key header"
            raise ExecutionInputValidationError(message=message)
        input_value = _input_value(request.body, request.content_type)
        event = TriggerEvent(
            channel=ExecutionSource.WEBHOOK,
            external_event_id=request.event_id,
            sender=TriggerActor(id=request.sender_id) if request.sender_id else None,
            conversation=(
                TriggerConversation(id=request.conversation_id)
                if request.conversation_id
                else None
            ),
            locale=request.locale,
            message=NodeValuePayload(kind=PortType.TEXT, value=input_value),
            occurred_at=datetime.now(tz=UTC),
            metadata={"content_type": request.content_type},
        )
        return (
            ChannelReceiveBatch(
                events=(
                    ChannelInboundEvent(
                        workflow_id=workflow.id,
                        user_id=workflow.owner_id,
                        input_value=input_value,
                        event=event,
                    ),
                )
            ),
        )

    async def deliver(self, context: ChannelDeliveryContext) -> None:
        """POST a finished execution to its configured callback URL."""
        url = context.output_node.data.get("webhook_url")
        if not isinstance(url, str) or not url.strip():
            return
        execution = context.execution
        await send_webhook(
            url=url.strip(),
            payload={
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": execution.status.value,
                "output": execution.output_data,
                "error": execution.error,
            },
        )


def _input_value(body: bytes, content_type: str | None) -> str:
    """Normalize a JSON or text body into the engine's text input contract."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        message = "Webhook body must be UTF-8 text or JSON"
        raise ExecutionInputValidationError(message=message) from exc

    media_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if text and (media_type == "application/json" or media_type.endswith("+json")):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            message = "Webhook body contains invalid JSON"
            raise ExecutionInputValidationError(message=message) from exc
        value = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
    else:
        value = text

    if len(value) > _MAX_INPUT_CHARS:
        message = f"Webhook input cannot exceed {_MAX_INPUT_CHARS} characters"
        raise ExecutionInputValidationError(message=message)
    return value


WEBHOOK_ADAPTER = WebhookChannelAdapter()
