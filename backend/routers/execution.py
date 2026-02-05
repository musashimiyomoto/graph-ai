"""Execution API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import execution as execution_dependency
from schemas import ExecutionCreate, ExecutionResponse, ExecutionUpdate

router = APIRouter(prefix="/executions", tags=["Executions"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_execution(
    data: Annotated[
        ExecutionCreate, Body(description="Data for creating an execution")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution_dependency.ExecutionUsecase,
        Depends(dependency=execution_dependency.get_execution_usecase),
    ],
) -> ExecutionResponse:
    """Create a new execution."""
    return ExecutionResponse.model_validate(
        await usecase.create_execution(
            session=session, **data.model_dump(exclude_none=True)
        )
    )


@router.get(path="")
async def list_executions(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution_dependency.ExecutionUsecase,
        Depends(dependency=execution_dependency.get_execution_usecase),
    ],
    workflow_id: Annotated[int | None, Query()] = None,
) -> list[ExecutionResponse]:
    """List executions, optionally filtered by workflow."""
    return [
        ExecutionResponse.model_validate(execution)
        for execution in await usecase.get_executions(
            session=session, workflow_id=workflow_id
        )
    ]


@router.get(path="/{execution_id}")
async def get_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution_dependency.ExecutionUsecase,
        Depends(dependency=execution_dependency.get_execution_usecase),
    ],
) -> ExecutionResponse:
    """Fetch an execution by ID."""
    return ExecutionResponse.model_validate(
        await usecase.get_execution(session=session, execution_id=execution_id)
    )


@router.patch(path="/{execution_id}")
async def update_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    data: Annotated[
        ExecutionUpdate, Body(description="Data for updating an execution")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution_dependency.ExecutionUsecase,
        Depends(dependency=execution_dependency.get_execution_usecase),
    ],
) -> ExecutionResponse:
    """Update an execution by ID."""
    return ExecutionResponse.model_validate(
        await usecase.update_execution(
            session=session, execution_id=execution_id, **data.model_dump()
        )
    )


@router.delete(path="/{execution_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_execution(
    execution_id: Annotated[int, Path(description="Execution ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        execution_dependency.ExecutionUsecase,
        Depends(dependency=execution_dependency.get_execution_usecase),
    ],
) -> JSONResponse:
    """Delete an execution by ID."""
    await usecase.delete_execution(session=session, execution_id=execution_id)
    return JSONResponse(content={"detail": "Execution deleted"})
