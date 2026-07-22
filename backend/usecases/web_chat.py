"""Public embedded web-chat use case."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from channels import receive_channel
from channels.web_chat import WEB_CHAT_ADAPTER, WebChatReceivePayload
from db.repositories import ExecutionRepository
from enums import ExecutionSource
from exceptions import WebChatNotFoundError
from schemas import ExecutionResponse, WebChatMessage


class WebChatUsecase:
    """Create and expose executions for a signed public web-chat surface."""

    def __init__(self) -> None:
        """Initialize repositories and execution orchestration."""
        self._execution_repository = ExecutionRepository()

    async def create_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        message: WebChatMessage,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> ExecutionResponse:
        """Queue one visitor message as a web-chat execution."""
        responses = await receive_channel(
            source=ExecutionSource.WEB_CHAT,
            session=session,
            enqueue=enqueue,
            payload=WebChatReceivePayload(token=token, message=message),
        )
        if len(responses) != 1:
            message_text = "Web-chat adapter must produce exactly one execution"
            raise RuntimeError(message_text)
        return responses[0]

    async def get_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        execution_id: int,
    ) -> ExecutionResponse:
        """Return a public execution only when it belongs to the signed workflow."""
        workflow = await WEB_CHAT_ADAPTER.enabled_workflow(session=session, token=token)
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id, workflow_id=workflow.id
        )
        if execution is None or execution.source is not ExecutionSource.WEB_CHAT:
            raise WebChatNotFoundError
        return ExecutionResponse.model_validate(execution)

    async def authorize_stream(
        self,
        *,
        session: AsyncSession,
        token: str,
        execution_id: int,
    ) -> int:
        """Validate public stream access and return the workflow owner ID."""
        workflow = await WEB_CHAT_ADAPTER.enabled_workflow(session=session, token=token)
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id, workflow_id=workflow.id
        )
        if execution is None or execution.source is not ExecutionSource.WEB_CHAT:
            raise WebChatNotFoundError
        return workflow.owner_id
