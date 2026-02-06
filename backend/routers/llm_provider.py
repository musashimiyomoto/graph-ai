"""LLM provider API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, llm_provider
from schemas import (
    LLMProviderCreate,
    LLMProviderResponse,
    LLMProviderUpdate,
    UserResponse,
)

router = APIRouter(prefix="/llm-providers", tags=["LLM Providers"])


@router.post(path="")
async def create_llm_provider(
    data: Annotated[
        LLMProviderCreate, Body(description="Data for creating an LLM provider")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> LLMProviderResponse:
    """Create a new LLM provider."""
    return LLMProviderResponse.model_validate(
        await usecase.create_llm_provider(
            session=session, user_id=current_user.id, **data.model_dump()
        )
    )


@router.get(path="")
async def list_llm_providers(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[LLMProviderResponse]:
    """List LLM providers for the current user."""
    return [
        LLMProviderResponse.model_validate(llm_provider)
        for llm_provider in await usecase.get_llm_providers(
            session=session, user_id=current_user.id
        )
    ]


@router.get(path="/{provider_id}")
async def get_llm_provider(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> LLMProviderResponse:
    """Fetch an LLM provider by ID."""
    return LLMProviderResponse.model_validate(
        await usecase.get_llm_provider(
            session=session, provider_id=provider_id, user_id=current_user.id
        )
    )


@router.patch(path="/{provider_id}")
async def update_llm_provider(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    data: Annotated[
        LLMProviderUpdate, Body(description="Data for updating an LLM provider")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> LLMProviderResponse:
    """Update an LLM provider by ID."""
    return LLMProviderResponse.model_validate(
        await usecase.update_llm_provider(
            session=session,
            provider_id=provider_id,
            user_id=current_user.id,
            **data.model_dump(),
        )
    )


@router.delete(path="/{provider_id}")
async def delete_llm_provider(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete an LLM provider by ID."""
    await usecase.delete_llm_provider(
        session=session, provider_id=provider_id, user_id=current_user.id
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "LLM provider deleted"}
    )
