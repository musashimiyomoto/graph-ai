"""User API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, user
from schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(path="/me")
async def get_me(
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> UserResponse:
    """Return the current user profile."""
    return current_user


@router.delete(path="/me")
async def delete_user(
    usecase: Annotated[user.UserUsecase, Depends(dependency=user.get_user_usecase)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete the current user."""
    await usecase.delete_user(session=session, user_id=current_user.id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "User deleted successfully"},
    )
