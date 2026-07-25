"""Public embedded web-chat use case."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from channels import receive_channel
from channels.web_chat import WEB_CHAT_ADAPTER, WebChatReceivePayload
from db.repositories import ConversationRepository, ExecutionRepository
from enums import ExecutionSource
from exceptions import WebChatNotFoundError
from schemas import ExecutionResponse, WebChatExecutionResponse, WebChatMessage


class WebChatUsecase:
    """Create and expose executions for a signed public web-chat surface."""

    def __init__(self) -> None:
        """Initialize repositories and execution orchestration."""
        self._execution_repository = ExecutionRepository()
        self._conversation_repository = ConversationRepository()

    async def create_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        message: WebChatMessage,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> WebChatExecutionResponse:
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
        return await self._public_response(
            session=session,
            workflow_id=responses[0].workflow_id,
            execution_id=responses[0].id,
        )

    async def get_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        execution_id: int,
        session_id: str,
    ) -> WebChatExecutionResponse:
        """Return a public execution only when it belongs to the signed workflow."""
        workflow = await WEB_CHAT_ADAPTER.enabled_workflow(session=session, token=token)
        await self._authorize_session_execution(
            session=session,
            workflow_id=workflow.id,
            execution_id=execution_id,
            session_id=session_id,
        )
        return await self._public_response(
            session=session,
            workflow_id=workflow.id,
            execution_id=execution_id,
        )

    async def authorize_stream(
        self,
        *,
        session: AsyncSession,
        token: str,
        execution_id: int,
        session_id: str,
    ) -> int:
        """Validate public stream access and return the workflow owner ID."""
        workflow = await WEB_CHAT_ADAPTER.enabled_workflow(session=session, token=token)
        await self._authorize_session_execution(
            session=session,
            workflow_id=workflow.id,
            execution_id=execution_id,
            session_id=session_id,
        )
        return workflow.owner_id

    async def _authorize_session_execution(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        execution_id: int,
        session_id: str,
    ) -> None:
        """Require the opaque session to own the requested public execution."""
        conversation = await self._conversation_repository.get_by(
            session=session,
            workflow_id=workflow_id,
            channel=ExecutionSource.WEB_CHAT,
            public_id=session_id,
        )
        execution = await self._execution_repository.get_by(
            session=session,
            id=execution_id,
            workflow_id=workflow_id,
        )
        if (
            conversation is None
            or execution is None
            or execution.source is not ExecutionSource.WEB_CHAT
            or execution.conversation_id != conversation.id
        ):
            raise WebChatNotFoundError

    async def _public_response(
        self,
        *,
        session: AsyncSession,
        workflow_id: int,
        execution_id: int,
    ) -> WebChatExecutionResponse:
        """Attach the conversation's opaque public session to an execution."""
        execution = await self._execution_repository.get_by(
            session=session,
            id=execution_id,
            workflow_id=workflow_id,
        )
        if (
            execution is None
            or execution.source is not ExecutionSource.WEB_CHAT
            or execution.conversation_id is None
        ):
            raise WebChatNotFoundError
        conversation = await self._conversation_repository.get_by(
            session=session,
            id=execution.conversation_id,
            workflow_id=workflow_id,
        )
        if conversation is None:
            raise WebChatNotFoundError
        return WebChatExecutionResponse(
            **ExecutionResponse.model_validate(execution).model_dump(),
            session_id=conversation.public_id,
        )
