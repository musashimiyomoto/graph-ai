"""Auth API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db
from schemas import Login, Token, UserCreate, UserResponse
from settings import auth_settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(path="/login")
async def login(
    data: Annotated[Login, Body(description="Data for login")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> Token:
    """Authenticate a user and return a token."""
    return Token(
        access_token=await usecase.login(session=session, **data.model_dump()),
        token_type=auth_settings.token_type,
    )


@router.post(path="/register")
async def register(
    data: Annotated[UserCreate, Body(description="Data for register")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[auth.AuthUsecase, Depends(dependency=auth.get_auth_usecase)],
) -> UserResponse:
    """Register a new user."""
    return UserResponse.model_validate(
        await usecase.register(session=session, **data.model_dump(exclude_none=True))
    )
