"""LLM provider API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import auth, db, llm_provider
from llm import (
    ChatMessage as LLMChatMessage,
)
from llm import (
    ChatRequest as LLMChatRequest,
)
from llm import (
    EmbeddingRequest as LLMEmbeddingRequest,
)
from schemas import (
    LLMProviderChatRequest,
    LLMProviderChatResponse,
    LLMProviderCreate,
    LLMProviderEmbeddingRequest,
    LLMProviderEmbeddingResponse,
    LLMProviderModelResponse,
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


@router.get(path="/{provider_id}/models")
async def list_provider_models(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[LLMProviderModelResponse]:
    """List available models for an LLM provider."""
    return [
        LLMProviderModelResponse.model_validate(model)
        for model in await usecase.get_models(
            session=session, provider_id=provider_id, user_id=current_user.id
        )
    ]


@router.post(path="/{provider_id}/chat")
async def chat_provider(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    data: Annotated[LLMProviderChatRequest, Body(description="Chat request payload")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> LLMProviderChatResponse:
    """Send chat messages to an LLM provider."""
    request = LLMChatRequest(
        model=data.model,
        messages=[
            LLMChatMessage(role=message.role, content=message.content)
            for message in data.messages
        ],
        options=data.options,
        stream=data.stream,
    )
    response = await usecase.chat(
        session=session,
        provider_id=provider_id,
        user_id=current_user.id,
        request=request,
    )
    return LLMProviderChatResponse.model_validate(response.raw)


@router.post(path="/{provider_id}/embeddings")
async def embed_provider(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    data: Annotated[
        LLMProviderEmbeddingRequest, Body(description="Embedding request payload")
    ],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> LLMProviderEmbeddingResponse:
    """Generate embeddings from an LLM provider."""
    request = LLMEmbeddingRequest(
        model=data.model,
        prompt=data.prompt,
        options=data.options,
    )
    response = await usecase.embed(
        session=session,
        provider_id=provider_id,
        user_id=current_user.id,
        request=request,
    )
    return LLMProviderEmbeddingResponse.model_validate(response.raw)
