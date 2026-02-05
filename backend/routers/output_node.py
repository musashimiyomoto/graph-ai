"""Output node API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import output_node as output_node_dependency
from schemas import OutputNodeCreate, OutputNodeResponse, OutputNodeUpdate

router = APIRouter(prefix="/output-nodes", tags=["Output Nodes"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_output_node(
    data: Annotated[
        OutputNodeCreate, Body(description="Data for creating an output node")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        output_node_dependency.OutputNodeUsecase,
        Depends(dependency=output_node_dependency.get_output_node_usecase),
    ],
) -> OutputNodeResponse:
    """Create an output node configuration."""
    return OutputNodeResponse.model_validate(
        await usecase.create_output_node(session=session, **data.model_dump())
    )


@router.get(path="/{node_id}")
async def get_output_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        output_node_dependency.OutputNodeUsecase,
        Depends(dependency=output_node_dependency.get_output_node_usecase),
    ],
) -> OutputNodeResponse:
    """Fetch an output node configuration by node ID."""
    return OutputNodeResponse.model_validate(
        await usecase.get_output_node(session=session, node_id=node_id)
    )


@router.patch(path="/{node_id}")
async def update_output_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    data: Annotated[
        OutputNodeUpdate, Body(description="Data for updating an output node")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        output_node_dependency.OutputNodeUsecase,
        Depends(dependency=output_node_dependency.get_output_node_usecase),
    ],
) -> OutputNodeResponse:
    """Update an output node configuration by node ID."""
    return OutputNodeResponse.model_validate(
        await usecase.update_output_node(
            session=session, node_id=node_id, **data.model_dump()
        )
    )


@router.delete(path="/{node_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_output_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        output_node_dependency.OutputNodeUsecase,
        Depends(dependency=output_node_dependency.get_output_node_usecase),
    ],
) -> JSONResponse:
    """Delete an output node configuration by node ID."""
    await usecase.delete_output_node(session=session, node_id=node_id)
    return JSONResponse(content={"detail": "Output node deleted"})
