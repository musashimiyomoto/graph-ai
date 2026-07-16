"""Usage and audit API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, usage
from api.dependencies.pagination import Pagination, get_pagination
from schemas import AuditLogResponse, UsageSummaryResponse, UserResponse
from usecases import AuditUsecase, UsageUsecase

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get(path="")
async def get_usage_summary(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[UsageUsecase, Depends(dependency=usage.get_usage_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> UsageSummaryResponse:
    """Return the current user's usage and quota status for today."""
    return await usecase.get_summary(session=session, user_id=current_user.id)


@router.get(path="/audit")
async def list_audit_logs(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[AuditUsecase, Depends(dependency=usage.get_audit_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pagination: Annotated[Pagination, Depends(dependency=get_pagination)],
) -> list[AuditLogResponse]:
    """List the current user's audit trail, newest first."""
    return await usecase.get_audit_logs(
        session=session, user_id=current_user.id, pagination=pagination
    )
