"""Auth API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db
from schemas import LoginCreate, LoginResponse, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(path="/login")
async def login(
    data: Annotated[LoginCreate, Body(description="Data for login")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> LoginResponse:
    """Authenticate a user and return a token."""
    return await usecase.login(session=session, data=data)


@router.post(path="/register")
async def register(
    data: Annotated[UserCreate, Body(description="Data for register")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> UserResponse:
    """Register a new user."""
    return await usecase.register(session=session, data=data)
