"""Inbound webhook trigger use case."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from channels import receive_channel
from channels.webhook import WebhookInboundRequest, WebhookReceivePayload
from enums import ExecutionSource
from schemas import ExecutionResponse


class WebhookUsecase:
    """Queue signed public webhook requests through the channel runtime."""

    async def trigger(
        self,
        *,
        session: AsyncSession,
        token: str,
        request: WebhookInboundRequest,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> ExecutionResponse:
        """Validate and queue one webhook-sourced execution."""
        responses = await receive_channel(
            source=ExecutionSource.WEBHOOK,
            session=session,
            enqueue=enqueue,
            payload=WebhookReceivePayload(token=token, request=request),
        )
        if len(responses) != 1:
            message = "Webhook adapter must produce exactly one execution"
            raise RuntimeError(message)
        return responses[0]
