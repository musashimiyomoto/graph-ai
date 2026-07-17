"""Inbound webhook trigger use case."""

import json
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import NodeRepository, WorkflowRepository
from enums import ExecutionSource, InputNodeFormat, NodeType
from exceptions import ExecutionInputValidationError, WebhookNotFoundError
from schemas import ExecutionCreate, ExecutionInputPayload, ExecutionResponse
from usecases.execution import ExecutionTrigger, ExecutionUsecase
from utils.webhooks import parse_webhook_token

_MAX_INPUT_CHARS = 50_000


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
        body: bytes,
        content_type: str | None,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> ExecutionResponse:
        """Validate a public token and queue a webhook-sourced execution.

        Args:
            session: Database session.
            token: Signed workflow token from the URL.
            body: Raw request body.
            content_type: Request Content-Type header.
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

        return await self._execution_usecase.create_execution(
            session=session,
            user_id=workflow.owner_id,
            data=ExecutionCreate(
                workflow_id=workflow_id,
                input_data=ExecutionInputPayload(
                    value=self._input_value(body, content_type)
                ),
            ),
            enqueue=enqueue,
            trigger=ExecutionTrigger(source=ExecutionSource.WEBHOOK),
        )
