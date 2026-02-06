"""Execution API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, execution
from schemas import ExecutionCreate, ExecutionResponse, ExecutionUpdate, UserResponse

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
    return ExecutionResponse.model_validate(
        await usecase.create_execution(
            session=session,
            user_id=current_user.id,
            **data.model_dump(exclude_none=True),
        )
    )


@router.get(path="")
async def list_executions(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    workflow_id: Annotated[int, Query(gt=0)],
) -> list[ExecutionResponse]:
    """List executions, optionally filtered by workflow."""
    return [
        ExecutionResponse.model_validate(execution)
        for execution in await usecase.get_executions(
            session=session, user_id=current_user.id, workflow_id=workflow_id
        )
    ]


@router.get(path="/{execution_id}")
async def get_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> ExecutionResponse:
    """Fetch an execution by ID."""
    return ExecutionResponse.model_validate(
        await usecase.get_execution(
            session=session, execution_id=execution_id, user_id=current_user.id
        )
    )


@router.patch(path="/{execution_id}")
async def update_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    data: Annotated[
        ExecutionUpdate, Body(description="Data for updating an execution")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> ExecutionResponse:
    """Update an execution by ID."""
    return ExecutionResponse.model_validate(
        await usecase.update_execution(
            session=session,
            execution_id=execution_id,
            user_id=current_user.id,
            **data.model_dump(),
        )
    )


@router.delete(path="/{execution_id}")
async def delete_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution.ExecutionUsecase,
        Depends(dependency=execution.get_execution_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete an execution by ID."""
    await usecase.delete_execution(
        session=session, execution_id=execution_id, user_id=current_user.id
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Execution deleted"}
    )
