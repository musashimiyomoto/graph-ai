"""LLM provider API routes."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.dependencies import auth, db, llm_provider, queue
from llm.ollama_catalog import OLLAMA_MODEL_CATALOG
from schemas import (
    LLMProviderCreate,
    LLMProviderModelResponse,
    LLMProviderResponse,
    LLMProviderUpdate,
    OllamaCatalogEntry,
    OllamaModelPullRequest,
    OllamaModelPullResponse,
    UserResponse,
)
from streaming import read_pull_snapshot, subscribe_pull_progress

router = APIRouter(prefix="/llm-providers", tags=["LLM Providers"])

# How long to wait for a live progress frame before re-checking the snapshot
# key, so a terminal frame published between snapshot read and subscribe can't
# leave the stream hanging.
_PULL_POLL_SECONDS = 2


async def _pull_event_stream(pool: ArqRedis, job_id: str) -> AsyncIterator[str]:
    """Yield SSE ``data:`` frames for a model pull until it finishes."""

    def frame(payload: dict[str, object]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    snapshot = await read_pull_snapshot(pool, job_id)
    if snapshot is not None:
        yield frame(snapshot)
        if snapshot.get("done"):
            return

    progress = subscribe_pull_progress(pool, job_id)
    try:
        while True:
            try:
                async with asyncio.timeout(_PULL_POLL_SECONDS):
                    payload = await anext(progress)
            except TimeoutError:
                snap = await read_pull_snapshot(pool, job_id)
                if snap is not None and snap.get("done"):
                    yield frame(snap)
                    return
                continue
            except StopAsyncIteration:
                return
            yield frame(payload)
            if payload.get("done"):
                return
    finally:
        await progress.aclose()


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
    return await usecase.create_llm_provider(
        session=session, user_id=current_user.id, data=data
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
    return await usecase.get_llm_providers(session=session, user_id=current_user.id)


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
    return await usecase.update_llm_provider(
        session=session, provider_id=provider_id, user_id=current_user.id, data=data
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
    return await usecase.get_models(
        session=session, provider_id=provider_id, user_id=current_user.id
    )


@router.get(path="/model-catalog")
async def get_model_catalog(
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[OllamaCatalogEntry]:
    """Return the curated catalog of pullable Ollama models."""
    del current_user
    return OLLAMA_MODEL_CATALOG


@router.post(path="/{provider_id}/models", status_code=status.HTTP_202_ACCEPTED)
async def pull_provider_model(  # noqa: PLR0913 — FastAPI deps + path/body params
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    data: Annotated[OllamaModelPullRequest, Body(description="Model to pull")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> OllamaModelPullResponse:
    """Queue a background pull of an Ollama model."""
    return await usecase.start_model_pull(
        session=session,
        provider_id=provider_id,
        user_id=current_user.id,
        model=data.model,
        pool=pool,
    )


@router.get(path="/{provider_id}/models/pull/{job_id}/stream")
async def stream_provider_model_pull(  # noqa: PLR0913 — FastAPI deps + path params
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    job_id: Annotated[str, Path(description="Pull job ID")],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(dependency=db.get_session_factory)
    ],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
) -> StreamingResponse:
    """Stream live model-pull progress as Server-Sent Events."""
    # Validate ownership up front on a short-lived session so a missing/forbidden
    # provider returns a proper error rather than failing mid-stream (and so the
    # DB connection isn't pinned for the whole pull).
    async with session_factory() as session:
        await usecase.get_llm_provider(
            session=session, provider_id=provider_id, user_id=current_user.id
        )
    return StreamingResponse(
        _pull_event_stream(pool, job_id), media_type="text/event-stream"
    )


@router.delete(path="/{provider_id}/models")
async def delete_provider_model(
    provider_id: Annotated[int, Path(description="LLM provider ID", gt=0)],
    model: Annotated[str, Query(description="Model name/tag to delete", min_length=1)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        llm_provider.LLMProviderUsecase,
        Depends(dependency=llm_provider.get_llm_provider_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete a model from an Ollama provider."""
    await usecase.delete_model(
        session=session,
        provider_id=provider_id,
        user_id=current_user.id,
        model=model,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Model deleted"}
    )
