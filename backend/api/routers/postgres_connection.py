"""Saved PostgreSQL connection API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, postgres_connection
from schemas import (
    PostgresConnectionCreate,
    PostgresConnectionResponse,
    UserResponse,
)

router = APIRouter(prefix="/postgres-connections", tags=["PostgreSQL Connections"])


@router.post(path="")
async def create_connection(
    data: Annotated[PostgresConnectionCreate, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        postgres_connection.PostgresConnectionUsecase,
        Depends(dependency=postgres_connection.get_postgres_connection_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> PostgresConnectionResponse:
    """Create a saved PostgreSQL connection."""
    return await usecase.create_connection(
        session=session, user_id=current_user.id, data=data
    )


@router.get(path="")
async def list_connections(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        postgres_connection.PostgresConnectionUsecase,
        Depends(dependency=postgres_connection.get_postgres_connection_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[PostgresConnectionResponse]:
    """List saved PostgreSQL connections."""
    return await usecase.list_connections(session=session, user_id=current_user.id)


@router.delete(path="/{connection_id}")
async def delete_connection(
    connection_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        postgres_connection.PostgresConnectionUsecase,
        Depends(dependency=postgres_connection.get_postgres_connection_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete a saved PostgreSQL connection."""
    await usecase.delete_connection(
        session=session, user_id=current_user.id, connection_id=connection_id
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "PostgreSQL connection deleted"},
    )
