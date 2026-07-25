"""Unified encrypted connection and OAuth routes."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, connection, db
from schemas import (
    ConnectionCreate,
    ConnectionOAuthCallbackResponse,
    ConnectionOAuthStart,
    ConnectionOAuthStartResponse,
    ConnectionResponse,
    UserResponse,
)

router = APIRouter(prefix="/connections", tags=["Connections"])


@dataclass(frozen=True)
class _ConnectionDependencies:
    """Dependencies shared by authenticated connection routes."""

    session: AsyncSession
    usecase: connection.ConnectionUsecase
    user: UserResponse


def _get_connection_dependencies(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        connection.ConnectionUsecase,
        Depends(dependency=connection.get_connection_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> _ConnectionDependencies:
    """Bundle authenticated connection route dependencies."""
    return _ConnectionDependencies(session=session, usecase=usecase, user=current_user)


@router.post(path="")
async def create_connection(
    data: Annotated[ConnectionCreate, Body()],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> ConnectionResponse:
    """Create an encrypted API-key or OAuth connection."""
    return await dependencies.usecase.create_connection(
        session=dependencies.session,
        user_id=dependencies.user.id,
        data=data,
    )


@router.get(path="")
async def list_connections(
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> list[ConnectionResponse]:
    """List owned connection metadata without secrets."""
    return await dependencies.usecase.list_connections(
        session=dependencies.session,
        user_id=dependencies.user.id,
    )


@router.get(path="/oauth/callback")
async def complete_oauth(
    state_value: Annotated[str, Query(alias="state", min_length=16, max_length=512)],
    code: Annotated[str, Query(min_length=1, max_length=4096)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        connection.ConnectionUsecase,
        Depends(dependency=connection.get_connection_usecase),
    ],
) -> ConnectionOAuthCallbackResponse:
    """Consume a bearer OAuth state and exchange the provider code."""
    return await usecase.complete_oauth(session=session, state=state_value, code=code)


@router.post(path="/{connection_id}/oauth/start")
async def start_oauth(
    connection_id: Annotated[int, Path(gt=0)],
    data: Annotated[ConnectionOAuthStart, Body()],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> ConnectionOAuthStartResponse:
    """Start an OAuth authorization-code flow with PKCE and hashed state."""
    return await dependencies.usecase.start_oauth(
        session=dependencies.session,
        user_id=dependencies.user.id,
        connection_id=connection_id,
        data=data,
    )


@router.post(path="/{connection_id}/refresh")
async def refresh_oauth(
    connection_id: Annotated[int, Path(gt=0)],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> ConnectionResponse:
    """Refresh an OAuth access token explicitly."""
    return await dependencies.usecase.refresh_oauth(
        session=dependencies.session,
        user_id=dependencies.user.id,
        connection_id=connection_id,
    )


@router.post(path="/{connection_id}/health")
async def check_connection_health(
    connection_id: Annotated[int, Path(gt=0)],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> ConnectionResponse:
    """Run a credential-aware health check."""
    return await dependencies.usecase.check_health(
        session=dependencies.session,
        user_id=dependencies.user.id,
        connection_id=connection_id,
    )


@router.post(path="/{connection_id}/revoke")
async def revoke_connection(
    connection_id: Annotated[int, Path(gt=0)],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> ConnectionResponse:
    """Revoke provider credentials when supported and always clear them locally."""
    return await dependencies.usecase.revoke_connection(
        session=dependencies.session,
        user_id=dependencies.user.id,
        connection_id=connection_id,
    )


@router.delete(path="/{connection_id}")
async def delete_connection(
    connection_id: Annotated[int, Path(gt=0)],
    dependencies: Annotated[
        _ConnectionDependencies, Depends(dependency=_get_connection_dependencies)
    ],
) -> JSONResponse:
    """Delete an owned connection."""
    await dependencies.usecase.delete_connection(
        session=dependencies.session,
        user_id=dependencies.user.id,
        connection_id=connection_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Connection deleted"},
    )
