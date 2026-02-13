"""Execution API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, execution
from schemas import ExecutionCreate, ExecutionResponse, UserResponse

router = APIRouter(prefix="/executions", tags=["Executions"])


@router.post(path="")
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
) -> ExecutionResponse:
    """Create a new execution."""
    return await usecase.create_execution(
        session=session, user_id=current_user.id, data=data
    )


@router.get(path="")
async def list_executions(
    workflow_id: Annotated[int, Query(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[ExecutionResponse]:
    """List executions, optionally filtered by workflow."""
    return await usecase.get_executions(
        session=session, user_id=current_user.id, workflow_id=workflow_id
    )
