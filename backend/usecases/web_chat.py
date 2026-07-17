"""Public embedded web-chat use case."""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Workflow
from db.repositories import ExecutionRepository, NodeRepository, WorkflowRepository
from enums import ExecutionSource, InputNodeFormat, NodeType, OutputNodeFormat
from exceptions import WebChatNotFoundError
from schemas import (
    ExecutionCreate,
    ExecutionInputPayload,
    ExecutionResponse,
    WebChatMessage,
)
from usecases.execution import ExecutionTrigger, ExecutionUsecase
from utils.web_chat import parse_web_chat_token


class WebChatUsecase:
    """Create and expose executions for a signed public web-chat surface."""

    def __init__(self) -> None:
        """Initialize repositories and execution orchestration."""
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._execution_repository = ExecutionRepository()
        self._execution_usecase = ExecutionUsecase()

    async def _get_enabled_workflow(
        self, session: AsyncSession, token: str
    ) -> Workflow:
        """Resolve a token and require matching web-chat Input and Output nodes."""
        workflow_id = parse_web_chat_token(token)
        if workflow_id is None:
            raise WebChatNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id
        )
        if workflow is None:
            raise WebChatNotFoundError

        input_node = await self._node_repository.get_by(
            session=session,
            workflow_id=workflow_id,
            type=NodeType.INPUT,
            parent_node_id=None,
        )
        output_node = await self._node_repository.get_by(
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

    async def create_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        message: WebChatMessage,
        enqueue: Callable[[int], Awaitable[None]],
    ) -> ExecutionResponse:
        """Queue one visitor message as a web-chat execution."""
        workflow = await self._get_enabled_workflow(session=session, token=token)
        return await self._execution_usecase.create_execution(
            session=session,
            user_id=workflow.owner_id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value=message.value),
            ),
            enqueue=enqueue,
            trigger=ExecutionTrigger(source=ExecutionSource.WEB_CHAT),
        )

    async def get_execution(
        self,
        *,
        session: AsyncSession,
        token: str,
        execution_id: int,
    ) -> ExecutionResponse:
        """Return a public execution only when it belongs to the signed workflow."""
        workflow = await self._get_enabled_workflow(session=session, token=token)
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
        workflow = await self._get_enabled_workflow(session=session, token=token)
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id, workflow_id=workflow.id
        )
        if execution is None or execution.source is not ExecutionSource.WEB_CHAT:
            raise WebChatNotFoundError
        return workflow.owner_id
