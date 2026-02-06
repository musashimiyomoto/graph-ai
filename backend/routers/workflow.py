"""Workflow API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, workflow
from schemas import UserResponse, WorkflowCreate, WorkflowResponse, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post(path="")
async def create_workflow(
    data: Annotated[WorkflowCreate, Body(description="Data for creating a workflow")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowUsecase,
        Depends(dependency=workflow.get_workflow_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> WorkflowResponse:
    """Create a workflow."""
    return WorkflowResponse.model_validate(
        await usecase.create_workflow(
            session=session, user_id=current_user.id, name=data.name
        )
    )


@router.get(path="")
async def list_workflows(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowUsecase,
        Depends(dependency=workflow.get_workflow_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[WorkflowResponse]:
    """List workflows for the current user."""
    return [
        WorkflowResponse.model_validate(workflow)
        for workflow in await usecase.get_workflows(
            session=session, user_id=current_user.id
        )
    ]


@router.get(path="/{workflow_id}")
async def get_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowUsecase,
        Depends(dependency=workflow.get_workflow_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> WorkflowResponse:
    """Fetch a workflow by ID."""
    return WorkflowResponse.model_validate(
        await usecase.get_workflow(
            session=session, workflow_id=workflow_id, user_id=current_user.id
        )
    )


@router.patch(path="/{workflow_id}")
async def update_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    data: Annotated[WorkflowUpdate, Body(description="Data for updating a workflow")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowUsecase,
        Depends(dependency=workflow.get_workflow_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> WorkflowResponse:
    """Update a workflow by ID."""
    return WorkflowResponse.model_validate(
        await usecase.update_workflow(
            session=session,
            workflow_id=workflow_id,
            user_id=current_user.id,
            **data.model_dump(),
        )
    )


@router.delete(path="/{workflow_id}")
async def delete_workflow(
    workflow_id: Annotated[int, Path(description="Workflow ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowUsecase,
        Depends(dependency=workflow.get_workflow_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete a workflow by ID."""
    await usecase.delete_workflow(
        session=session, workflow_id=workflow_id, user_id=current_user.id
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Workflow deleted"}
    )
