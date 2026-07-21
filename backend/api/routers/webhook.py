"""Public workflow webhook routes."""

from http import HTTPStatus
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import db, queue, webhook
from exceptions import ExecutionInputValidationError
from schemas import ExecutionResponse

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
_MAX_BODY_BYTES = 200_000


async def _read_limited_body(request: Request) -> bytes:
    """Read a bounded public request body without buffering unlimited input."""
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_BODY_BYTES:
            message = f"Webhook body cannot exceed {_MAX_BODY_BYTES} bytes"
            raise ExecutionInputValidationError(message=message)
    return bytes(body)


@router.post(path="/{token}", status_code=HTTPStatus.ACCEPTED)
async def trigger_webhook(
    token: Annotated[str, Path(description="Signed workflow webhook token")],
    request: Request,
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        webhook.WebhookUsecase,
        Depends(dependency=webhook.get_webhook_usecase),
    ],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> ExecutionResponse:
    """Queue a workflow execution from an unauthenticated signed webhook."""

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await pool.enqueue_job(
            "run_execution_task",
            execution_id,
            _job_id=f"execution:{execution_id}",
        )

    return await usecase.trigger(
        session=session,
        token=token,
        request=webhook.WebhookInboundRequest(
            body=await _read_limited_body(request),
            content_type=request.headers.get("content-type"),
            event_id=request.headers.get("idempotency-key"),
            sender_id=request.headers.get("x-sender-id"),
            conversation_id=request.headers.get("x-conversation-id"),
            locale=request.headers.get("content-language"),
        ),
        enqueue=enqueue,
    )
