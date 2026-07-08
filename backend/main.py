"""Graph AI Backend entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from api.routers import (
    auth,
    edge,
    execution,
    health,
    llm_provider,
    node,
    telegram_bot,
    user,
    vector,
    workflow,
)
from exceptions import BaseError
from logging_config import configure_logging
from settings import cors_settings, redis_settings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the ARQ Redis pool and shared Redis client lifecycle.

    Args:
        app: The FastAPI application.

    Yields:
        Control back to the application while the pool is open.

    """
    app.state.arq_pool = await create_pool(redis_settings.arq)
    app.state.redis_client = Redis(
        host=redis_settings.host,
        port=redis_settings.port,
        db=redis_settings.db,
    )
    try:
        yield
    finally:
        await app.state.arq_pool.aclose()
        await app.state.redis_client.aclose()


app = FastAPI(title="Graph AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]
    allow_origins=cors_settings.origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(exc_class_or_status_code=BaseError)
async def handle_base_error(_: Request, exc: BaseError) -> JSONResponse:
    """Handle domain errors as JSON responses.

    Args:
        _: The incoming request.
        exc: The domain error.

    Returns:
        A JSON response with the error detail.

    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(router=health.router)
app.include_router(router=auth.router)
app.include_router(router=user.router)
app.include_router(router=workflow.router)
app.include_router(router=node.router)
app.include_router(router=edge.router)
app.include_router(router=execution.router)
app.include_router(router=llm_provider.router)
app.include_router(router=telegram_bot.router)
app.include_router(router=vector.router)
