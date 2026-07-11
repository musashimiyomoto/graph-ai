"""Workflow template API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, workflow
from schemas import (
    UserResponse,
    WorkflowResponse,
    WorkflowTemplateInstantiateRequest,
    WorkflowTemplateResponse,
)

router = APIRouter(prefix="/workflow-templates", tags=["Workflow Templates"])


@router.get(path="")
async def list_workflow_templates(
    usecase: Annotated[
        workflow.WorkflowTransferUsecase,
        Depends(dependency=workflow.get_workflow_transfer_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[WorkflowTemplateResponse]:
    """List the global workflow template catalog."""
    del current_user  # auth-gated, but templates are the same for everyone
    return usecase.list_templates()


@router.post(path="/{template_key}/instantiate")
async def instantiate_workflow_template(
    template_key: Annotated[str, Path(description="Template key")],
    data: Annotated[
        WorkflowTemplateInstantiateRequest,
        Body(description="Optional name override for the new workflow"),
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        workflow.WorkflowTransferUsecase,
        Depends(dependency=workflow.get_workflow_transfer_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> WorkflowResponse:
    """Create a new workflow from a template's graph."""
    return await usecase.instantiate_template(
        session=session,
        user_id=current_user.id,
        key=template_key,
        name=data.name,
    )
