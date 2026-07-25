"""Authenticated typed durable state routes."""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, state
from api.dependencies.pagination import Pagination, get_pagination
from enums import StateScope
from schemas import (
    STATE_KEY_PATTERN,
    StateDelete,
    StateEntryResponse,
    StateHistoryResponse,
    StateMutation,
    UserResponse,
)
from usecases import StateAccess

router = APIRouter(prefix="/executions/{execution_id}/state", tags=["State"])


@dataclass(frozen=True)
class _StateDependencies:
    """Dependencies shared by authenticated state routes."""

    session: AsyncSession
    usecase: state.StateUsecase
    user: UserResponse


def _get_state_dependencies(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[state.StateUsecase, Depends(dependency=state.get_state_usecase)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> _StateDependencies:
    """Bundle state route dependencies."""
    return _StateDependencies(session=session, usecase=usecase, user=current_user)


def _access(
    *, execution_id: int, scope: StateScope, key: str, user_id: int
) -> StateAccess:
    """Build the state-usecase access context from bound route values."""
    return StateAccess(
        user_id=user_id,
        execution_id=execution_id,
        scope=scope,
        key=key,
    )


@router.get(path="/{scope}/{key}/history")
async def get_state_history(
    execution_id: Annotated[int, Path(gt=0)],
    scope: Annotated[StateScope, Path()],
    key: Annotated[str, Path(pattern=STATE_KEY_PATTERN)],
    pagination: Annotated[Pagination, Depends(dependency=get_pagination)],
    dependencies: Annotated[
        _StateDependencies, Depends(dependency=_get_state_dependencies)
    ],
) -> list[StateHistoryResponse]:
    """Return append-only mutation history for one scoped state key."""
    return await dependencies.usecase.history(
        session=dependencies.session,
        access=_access(
            execution_id=execution_id,
            scope=scope,
            key=key,
            user_id=dependencies.user.id,
        ),
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(path="/{scope}/{key}")
async def get_state_entry(
    execution_id: Annotated[int, Path(gt=0)],
    scope: Annotated[StateScope, Path()],
    key: Annotated[str, Path(pattern=STATE_KEY_PATTERN)],
    dependencies: Annotated[
        _StateDependencies, Depends(dependency=_get_state_dependencies)
    ],
) -> StateEntryResponse:
    """Read a non-expired typed state value."""
    return await dependencies.usecase.get(
        session=dependencies.session,
        access=_access(
            execution_id=execution_id,
            scope=scope,
            key=key,
            user_id=dependencies.user.id,
        ),
    )


@router.put(path="/{scope}/{key}")
async def set_state_entry(
    execution_id: Annotated[int, Path(gt=0)],
    scope: Annotated[StateScope, Path()],
    key: Annotated[str, Path(pattern=STATE_KEY_PATTERN)],
    mutation: Annotated[StateMutation, Body()],
    dependencies: Annotated[
        _StateDependencies, Depends(dependency=_get_state_dependencies)
    ],
) -> StateEntryResponse:
    """Create or replace a typed state value."""
    return await dependencies.usecase.set(
        session=dependencies.session,
        access=_access(
            execution_id=execution_id,
            scope=scope,
            key=key,
            user_id=dependencies.user.id,
        ),
        mutation=mutation,
    )


@router.delete(path="/{scope}/{key}", status_code=HTTPStatus.NO_CONTENT)
async def delete_state_entry(
    execution_id: Annotated[int, Path(gt=0)],
    scope: Annotated[StateScope, Path()],
    key: Annotated[str, Path(pattern=STATE_KEY_PATTERN)],
    deletion: Annotated[StateDelete, Body()],
    dependencies: Annotated[
        _StateDependencies, Depends(dependency=_get_state_dependencies)
    ],
) -> Response:
    """Delete a typed state value while retaining its history."""
    await dependencies.usecase.delete(
        session=dependencies.session,
        access=_access(
            execution_id=execution_id,
            scope=scope,
            key=key,
            user_id=dependencies.user.id,
        ),
        expected_version=deletion.expected_version,
    )
    return Response(status_code=HTTPStatus.NO_CONTENT)
