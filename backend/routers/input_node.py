"""Input node API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import input_node as input_node_dependency
from schemas import InputNodeCreate, InputNodeResponse, InputNodeUpdate

router = APIRouter(prefix="/input-nodes", tags=["Input Nodes"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_input_node(
    data: Annotated[
        InputNodeCreate, Body(description="Data for creating an input node")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        input_node_dependency.InputNodeUsecase,
        Depends(dependency=input_node_dependency.get_input_node_usecase),
    ],
) -> InputNodeResponse:
    """Create an input node configuration."""
    return InputNodeResponse.model_validate(
        await usecase.create_input_node(session=session, **data.model_dump())
    )


@router.get(path="/{node_id}")
async def get_input_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        input_node_dependency.InputNodeUsecase,
        Depends(dependency=input_node_dependency.get_input_node_usecase),
    ],
) -> InputNodeResponse:
    """Fetch an input node configuration by node ID."""
    return InputNodeResponse.model_validate(
        await usecase.get_input_node(session=session, node_id=node_id)
    )


@router.patch(path="/{node_id}")
async def update_input_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    data: Annotated[
        InputNodeUpdate, Body(description="Data for updating an input node")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        input_node_dependency.InputNodeUsecase,
        Depends(dependency=input_node_dependency.get_input_node_usecase),
    ],
) -> InputNodeResponse:
    """Update an input node configuration by node ID."""
    return InputNodeResponse.model_validate(
        await usecase.update_input_node(
            session=session, node_id=node_id, **data.model_dump()
        )
    )


@router.delete(path="/{node_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_input_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        input_node_dependency.InputNodeUsecase,
        Depends(dependency=input_node_dependency.get_input_node_usecase),
    ],
) -> JSONResponse:
    """Delete an input node configuration by node ID."""
    await usecase.delete_input_node(session=session, node_id=node_id)
    return JSONResponse(content={"detail": "Input node deleted"})
