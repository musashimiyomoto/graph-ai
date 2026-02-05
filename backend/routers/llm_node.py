"""LLM node API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import db
from dependencies import llm_node as llm_node_dependency
from schemas import LLMNodeCreate, LLMNodeResponse, LLMNodeUpdate

router = APIRouter(prefix="/llm-nodes", tags=["LLM Nodes"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def create_llm_node(
    data: Annotated[LLMNodeCreate, Body(description="Data for creating an LLM node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_node_dependency.LLMNodeUsecase,
        Depends(dependency=llm_node_dependency.get_llm_node_usecase),
    ],
) -> LLMNodeResponse:
    """Create an LLM node configuration."""
    return LLMNodeResponse.model_validate(
        await usecase.create_llm_node(session=session, **data.model_dump())
    )


@router.get(path="/{node_id}")
async def get_llm_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_node_dependency.LLMNodeUsecase,
        Depends(dependency=llm_node_dependency.get_llm_node_usecase),
    ],
) -> LLMNodeResponse:
    """Fetch an LLM node configuration by node ID."""
    return LLMNodeResponse.model_validate(
        await usecase.get_llm_node(session=session, node_id=node_id)
    )


@router.patch(path="/{node_id}")
async def update_llm_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    data: Annotated[LLMNodeUpdate, Body(description="Data for updating an LLM node")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_node_dependency.LLMNodeUsecase,
        Depends(dependency=llm_node_dependency.get_llm_node_usecase),
    ],
) -> LLMNodeResponse:
    """Update an LLM node configuration by node ID."""
    return LLMNodeResponse.model_validate(
        await usecase.update_llm_node(
            session=session, node_id=node_id, **data.model_dump()
        )
    )


@router.delete(path="/{node_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_llm_node(
    node_id: Annotated[int, Path(description="Node ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_node_dependency.LLMNodeUsecase,
        Depends(dependency=llm_node_dependency.get_llm_node_usecase),
    ],
) -> JSONResponse:
    """Delete an LLM node configuration by node ID."""
    await usecase.delete_llm_node(session=session, node_id=node_id)
    return JSONResponse(content={"detail": "LLM node deleted"})
