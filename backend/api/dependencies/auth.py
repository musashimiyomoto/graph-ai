"""Auth dependency providers."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import db
from schemas import UserResponse
from usecases import AuthUsecase

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(dependency=security)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> UserResponse:
    """Get the user.

    Dependencies:
        credentials: The credentials.
        session: The session.

    Returns:
        The user.

    """
    return UserResponse.model_validate(
        await AuthUsecase().get_current_user(
            token=credentials.credentials,
            session=session,
        )
    )


def get_auth_usecase() -> AuthUsecase:
    """Get the user auth usecase.

    Returns:
        The user auth usecase.

    """
    return AuthUsecase()
