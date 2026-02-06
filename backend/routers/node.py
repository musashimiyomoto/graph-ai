"""Node API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, node
from schemas import NodeCreate, NodeResponse, NodeUpdate, UserResponse

router = APIRouter(prefix="/nodes", tags=["Nodes"])


@router.post(path="")
async def create_node(
    data: Annotated[NodeCreate, Body(description="Data for creating a node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node.NodeUsecase,
        Depends(dependency=node.get_node_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> NodeResponse:
    """Create a node."""
    return NodeResponse.model_validate(
        await usecase.create_node(
            session=session, user_id=current_user.id, **data.model_dump()
        )
    )


@router.get(path="")
async def list_nodes(
    workflow_id: Annotated[int, Query(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node.NodeUsecase,
        Depends(dependency=node.get_node_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[NodeResponse]:
    """List nodes, optionally filtered by workflow."""
    return [
        NodeResponse.model_validate(node)
        for node in await usecase.get_nodes(
            session=session, user_id=current_user.id, workflow_id=workflow_id
        )
    ]


@router.get(path="/{node_id}")
async def get_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node.NodeUsecase,
        Depends(dependency=node.get_node_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> NodeResponse:
    """Fetch a node by ID."""
    return NodeResponse.model_validate(
        await usecase.get_node(
            session=session, node_id=node_id, user_id=current_user.id
        )
    )


@router.patch(path="/{node_id}")
async def update_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    data: Annotated[NodeUpdate, Body(description="Data for updating a node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node.NodeUsecase,
        Depends(dependency=node.get_node_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> NodeResponse:
    """Update a node by ID."""
    return NodeResponse.model_validate(
        await usecase.update_node(
            session=session,
            node_id=node_id,
            user_id=current_user.id,
            **data.model_dump(),
        )
    )


@router.delete(path="/{node_id}")
async def delete_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node.NodeUsecase,
        Depends(dependency=node.get_node_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete a node by ID."""
    await usecase.delete_node(session=session, node_id=node_id, user_id=current_user.id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Node deleted"}
    )
