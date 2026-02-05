"""Node API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import node as node_dependency
from schemas import NodeCreate, NodeResponse, NodeUpdate

router = APIRouter(prefix="/nodes", tags=["Nodes"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_node(
    data: Annotated[NodeCreate, Body(description="Data for creating a node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node_dependency.NodeUsecase,
        Depends(dependency=node_dependency.get_node_usecase),
    ],
) -> NodeResponse:
    """Create a node."""
    return NodeResponse.model_validate(
        await usecase.create_node(session=session, **data.model_dump())
    )


@router.get(path="")
async def list_nodes(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node_dependency.NodeUsecase,
        Depends(dependency=node_dependency.get_node_usecase),
    ],
    workflow_id: Annotated[int | None, Query()] = None,
) -> list[NodeResponse]:
    """List nodes, optionally filtered by workflow."""
    return [
        NodeResponse.model_validate(node)
        for node in await usecase.get_nodes(session=session, workflow_id=workflow_id)
    ]


@router.get(path="/{node_id}")
async def get_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node_dependency.NodeUsecase,
        Depends(dependency=node_dependency.get_node_usecase),
    ],
) -> NodeResponse:
    """Fetch a node by ID."""
    return NodeResponse.model_validate(
        await usecase.get_node(session=session, node_id=node_id)
    )


@router.patch(path="/{node_id}")
async def update_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    data: Annotated[NodeUpdate, Body(description="Data for updating a node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node_dependency.NodeUsecase,
        Depends(dependency=node_dependency.get_node_usecase),
    ],
) -> NodeResponse:
    """Update a node by ID."""
    return NodeResponse.model_validate(
        await usecase.update_node(session=session, node_id=node_id, **data.model_dump())
    )


@router.delete(path="/{node_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        node_dependency.NodeUsecase,
        Depends(dependency=node_dependency.get_node_usecase),
    ],
) -> JSONResponse:
    """Delete a node by ID."""
    await usecase.delete_node(session=session, node_id=node_id)
    return JSONResponse(content={"detail": "Node deleted"})
