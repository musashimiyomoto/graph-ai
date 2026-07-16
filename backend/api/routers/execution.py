"""Execution API routes."""

from http import HTTPStatus
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Body, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import auth, db, execution, queue
from api.dependencies.pagination import Pagination, get_pagination
from api.dependencies.quota import enforce_execution_quota
from schemas import (
    ExecutionCreate,
    ExecutionResponse,
    NodeExecutionResponse,
    UserResponse,
)
from usecases import ExecutionListFilter

router = APIRouter(prefix="/executions", tags=["Executions"])


@router.post(
    path="",
    status_code=HTTPStatus.ACCEPTED,
    dependencies=[Depends(dependency=enforce_execution_quota)],
)
async def create_execution(
    data: Annotated[
        ExecutionCreate, Body(description="Data for creating an execution")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> ExecutionResponse:
    """Queue a new execution for background running."""

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await pool.enqueue_job(
            "run_execution_task",
            execution_id,
            _job_id=f"execution:{execution_id}",
        )

    return await usecase.create_execution(
        session=session, user_id=current_user.id, data=data, enqueue=enqueue
    )


@router.get(path="")
async def list_executions(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pagination: Annotated[Pagination, Depends(dependency=get_pagination)],
    list_filter: Annotated[
        ExecutionListFilter, Depends(dependency=execution.get_execution_list_filter)
    ],
) -> list[ExecutionResponse]:
    """List executions for a workflow, newest first."""
    return await usecase.get_executions(
        session=session,
        user_id=current_user.id,
        list_filter=list_filter,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(path="/{execution_id}/nodes")
async def list_node_executions(
    execution_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pagination: Annotated[Pagination, Depends(dependency=get_pagination)],
) -> list[NodeExecutionResponse]:
    """List per-node results for an execution."""
    return await usecase.get_node_executions(
        session=session,
        execution_id=execution_id,
        user_id=current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(path="/{execution_id}/stream")
async def stream_execution(
    execution_id: Annotated[int, Path(gt=0)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(dependency=db.get_session_factory)
    ],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> StreamingResponse:
    """Stream execution status and live LLM tokens as Server-Sent Events."""
    # Validate ownership up front, on a short-lived session, so a missing/
    # forbidden execution returns a proper error response instead of failing
    # mid-stream.
    async with session_factory() as session:
        await usecase.get_execution(
            session=session, execution_id=execution_id, user_id=current_user.id
        )
    return StreamingResponse(
        usecase.stream_execution(
            session_factory=session_factory,
            execution_id=execution_id,
            user_id=current_user.id,
            pool=pool,
        ),
        media_type="text/event-stream",
    )
