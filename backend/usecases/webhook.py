"""Inbound webhook trigger use case."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import NodeRepository, WorkflowRepository
from enums import ExecutionSource, InputNodeFormat, NodeType, PortType
from exceptions import ExecutionInputValidationError, WebhookNotFoundError
from schemas import (
    ExecutionCreate,
    ExecutionInputPayload,
    ExecutionResponse,
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
)
from usecases.execution import ExecutionTrigger, ExecutionUsecase
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


class WebhookUsecase:
    """Business logic for public workflow webhook triggers."""

    def __init__(self) -> None:
        """Initialize repositories and execution orchestration."""
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._execution_usecase = ExecutionUsecase()

    @staticmethod
    def _input_value(body: bytes, content_type: str | None) -> str:
        """Normalize a JSON or text request body into the engine's text input.

        Args:
            body: Raw request body.
            content_type: Caller-provided Content-Type header.

        Returns:
            Text passed to the workflow Input node.

        Raises:
            ExecutionInputValidationError: If the body is malformed or too large.

        """
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

    async def trigger(
        self,
        *,
        session: AsyncSession,
        token: str,
        request: WebhookInboundRequest,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> ExecutionResponse:
        """Validate a public token and queue a webhook-sourced execution.

        Args:
            session: Database session.
            token: Signed workflow token from the URL.
            request: Body and normalized idempotency/sender headers.
            enqueue: Background execution enqueue callback.

        Returns:
            The queued execution.

        Raises:
            WebhookNotFoundError: If the token is invalid or webhook input is off.

        """
        workflow_id = parse_webhook_token(token)
        if workflow_id is None:
            raise WebhookNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id
        )
        if workflow is None:
            raise WebhookNotFoundError

        input_node = await self._node_repository.get_by(
            session=session,
            workflow_id=workflow_id,
            type=NodeType.INPUT,
            parent_node_id=None,
        )
        if (
            input_node is None
            or input_node.data.get("format") != InputNodeFormat.WEBHOOK.value
        ):
            raise WebhookNotFoundError

        if not request.event_id or len(request.event_id) > _MAX_EVENT_ID_CHARS:
            message = "Webhook requests require an Idempotency-Key header"
            raise ExecutionInputValidationError(message=message)

        input_value = self._input_value(request.body, request.content_type)

        return await self._execution_usecase.create_execution(
            session=session,
            user_id=workflow.owner_id,
            data=ExecutionCreate(
                workflow_id=workflow_id,
                input_data=ExecutionInputPayload(value=input_value),
            ),
            enqueue=enqueue,
            trigger=ExecutionTrigger(
                source=ExecutionSource.WEBHOOK,
                event=TriggerEvent(
                    channel=ExecutionSource.WEBHOOK,
                    external_event_id=request.event_id,
                    sender=(
                        TriggerActor(id=request.sender_id)
                        if request.sender_id
                        else None
                    ),
                    conversation=(
                        TriggerConversation(id=request.conversation_id)
                        if request.conversation_id
                        else None
                    ),
                    locale=request.locale,
                    message=NodeValuePayload(
                        kind=PortType.TEXT,
                        value=input_value,
                    ),
                    occurred_at=datetime.now(tz=UTC),
                    metadata={"content_type": request.content_type},
                ),
            ),
        )
