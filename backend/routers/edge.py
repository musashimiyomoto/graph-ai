"""Edge API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, edge
from schemas import EdgeCreate, EdgeResponse, EdgeUpdate, UserResponse

router = APIRouter(prefix="/edges", tags=["Edges"])


@router.post(path="")
async def create_edge(
    data: Annotated[EdgeCreate, Body(description="Data for creating an edge")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        edge.EdgeUsecase,
        Depends(dependency=edge.get_edge_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> EdgeResponse:
    """Create a new edge."""
    return EdgeResponse.model_validate(
        await usecase.create_edge(
            session=session, user_id=current_user.id, **data.model_dump()
        )
    )


@router.get(path="")
async def list_edges(
    workflow_id: Annotated[int, Query(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        edge.EdgeUsecase,
        Depends(dependency=edge.get_edge_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[EdgeResponse]:
    """List edges, optionally filtered by workflow."""
    return [
        EdgeResponse.model_validate(edge)
        for edge in await usecase.get_edges(
            session=session, user_id=current_user.id, workflow_id=workflow_id
        )
    ]


@router.patch(path="/{edge_id}")
async def update_edge(
    edge_id: Annotated[int, Path(description="Edge ID", gt=0)],
    data: Annotated[EdgeUpdate, Body(description="Data for updating an edge")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        edge.EdgeUsecase,
        Depends(dependency=edge.get_edge_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> EdgeResponse:
    """Update an edge by ID."""
    return EdgeResponse.model_validate(
        await usecase.update_edge(
            session=session,
            edge_id=edge_id,
            user_id=current_user.id,
            **data.model_dump(),
        )
    )


@router.delete(path="/{edge_id}")
async def delete_edge(
    edge_id: Annotated[int, Path(description="Edge ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        edge.EdgeUsecase,
        Depends(dependency=edge.get_edge_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete an edge by ID."""
    await usecase.delete_edge(session=session, edge_id=edge_id, user_id=current_user.id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Edge deleted"}
    )
