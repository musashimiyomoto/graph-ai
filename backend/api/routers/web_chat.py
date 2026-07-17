"""Public embedded web-chat routes."""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Body, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import db, queue, web_chat
from api.dependencies.execution import get_execution_usecase
from schemas import ExecutionResponse, WebChatMessage
from usecases import ExecutionUsecase

router = APIRouter(prefix="/web-chat", tags=["Web Chat"])


@dataclass(frozen=True)
class _StreamDependencies:
    """Dependencies shared by the public SSE stream route."""

    session_factory: async_sessionmaker[AsyncSession]
    web_chat_usecase: web_chat.WebChatUsecase
    execution_usecase: ExecutionUsecase
    pool: ArqRedis


def _get_stream_dependencies(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(dependency=db.get_session_factory)
    ],
    web_chat_usecase: Annotated[
        web_chat.WebChatUsecase,
        Depends(dependency=web_chat.get_web_chat_usecase),
    ],
    execution_usecase: Annotated[
        ExecutionUsecase,
        Depends(dependency=get_execution_usecase),
    ],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> _StreamDependencies:
    """Bundle public stream dependencies behind one route parameter."""
    return _StreamDependencies(
        session_factory=session_factory,
        web_chat_usecase=web_chat_usecase,
        execution_usecase=execution_usecase,
        pool=pool,
    )


@router.post(path="/{token}/executions", status_code=HTTPStatus.ACCEPTED)
async def create_web_chat_execution(
    token: Annotated[str, Path(description="Signed workflow web-chat token")],
    message: Annotated[WebChatMessage, Body(description="Visitor message")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        web_chat.WebChatUsecase,
        Depends(dependency=web_chat.get_web_chat_usecase),
    ],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> ExecutionResponse:
    """Queue a visitor message for the embedded chat."""

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await pool.enqueue_job(
            "run_execution_task",
            execution_id,
            _job_id=f"execution:{execution_id}",
        )

    return await usecase.create_execution(
        session=session, token=token, message=message, enqueue=enqueue
    )


@router.get(path="/{token}/executions/{execution_id}")
async def get_web_chat_execution(
    token: Annotated[str, Path(description="Signed workflow web-chat token")],
    execution_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        web_chat.WebChatUsecase,
        Depends(dependency=web_chat.get_web_chat_usecase),
    ],
) -> ExecutionResponse:
    """Return the current state of a public web-chat execution."""
    return await usecase.get_execution(
        session=session, token=token, execution_id=execution_id
    )


@router.get(path="/{token}/executions/{execution_id}/stream")
async def stream_web_chat_execution(
    token: Annotated[str, Path(description="Signed workflow web-chat token")],
    execution_id: Annotated[int, Path(gt=0)],
    dependencies: Annotated[
        _StreamDependencies, Depends(dependency=_get_stream_dependencies)
    ],
) -> StreamingResponse:
    """Stream public web-chat execution status and LLM tokens as SSE."""
    async with dependencies.session_factory() as session:
        owner_id = await dependencies.web_chat_usecase.authorize_stream(
            session=session, token=token, execution_id=execution_id
        )
    return StreamingResponse(
        dependencies.execution_usecase.stream_execution(
            session_factory=dependencies.session_factory,
            execution_id=execution_id,
            user_id=owner_id,
            pool=dependencies.pool,
        ),
        media_type="text/event-stream",
    )
