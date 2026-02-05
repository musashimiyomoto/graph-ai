"""Workflow API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import workflow as workflow_dependency
from schemas import WorkflowCreate, WorkflowResponse, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    data: Annotated[WorkflowCreate, Body(description="Data for creating a workflow")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow_dependency.WorkflowUsecase,
        Depends(dependency=workflow_dependency.get_workflow_usecase),
    ],
) -> WorkflowResponse:
    """Create a workflow."""
    return WorkflowResponse.model_validate(
        await usecase.create_workflow(session=session, **data.model_dump())
    )


@router.get(path="")
async def list_workflows(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow_dependency.WorkflowUsecase,
        Depends(dependency=workflow_dependency.get_workflow_usecase),
    ],
    owner_id: Annotated[int | None, Query()] = None,
) -> list[WorkflowResponse]:
    """List workflows, optionally filtered by owner."""
    return [
        WorkflowResponse.model_validate(workflow)
        for workflow in await usecase.get_workflows(session=session, owner_id=owner_id)
    ]


@router.get(path="/{workflow_id}")
async def get_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow_dependency.WorkflowUsecase,
        Depends(dependency=workflow_dependency.get_workflow_usecase),
    ],
) -> WorkflowResponse:
    """Fetch a workflow by ID."""
    return WorkflowResponse.model_validate(
        await usecase.get_workflow(session=session, workflow_id=workflow_id)
    )


@router.patch(path="/{workflow_id}")
async def update_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    data: Annotated[WorkflowUpdate, Body(description="Data for updating a workflow")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow_dependency.WorkflowUsecase,
        Depends(dependency=workflow_dependency.get_workflow_usecase),
    ],
) -> WorkflowResponse:
    """Update a workflow by ID."""
    return WorkflowResponse.model_validate(
        await usecase.update_workflow(
            session=session, workflow_id=workflow_id, **data.model_dump()
        )
    )


@router.delete(path="/{workflow_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow_dependency.WorkflowUsecase,
        Depends(dependency=workflow_dependency.get_workflow_usecase),
    ],
) -> JSONResponse:
    """Delete a workflow by ID."""
    await usecase.delete_workflow(session=session, workflow_id=workflow_id)
    return JSONResponse(content={"detail": "Workflow deleted"})
