"""Graph AI Backend entrypoint."""

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from api.metrics import http_request_duration_seconds, http_requests_total
from api.routers import (
    artifact,
    auth,
    channel,
    connection,
    edge,
    email_account,
    execution,
    health,
    llm_provider,
    mcp_server,
    metrics,
    node,
    postgres_connection,
    state,
    telegram_bot,
    usage,
    user,
    vector,
    web_chat,
    webhook,
    workflow,
    workflow_template,
)
from artifacts import artifact_store
from exceptions import BaseError
from logging_config import configure_logging
from observability import init_sentry
from settings import cors_settings, redis_settings

configure_logging()
init_sentry(component="api")


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
    await artifact_store.ensure_bucket()
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


def _route_label(request: Request) -> str:
    """Resolve a low-cardinality path label from the matched route template.

    Uses the route's path *template* (e.g. ``/executions/{execution_id}``)
    rather than the concrete URL, so per-id paths don't explode metric
    cardinality. Falls back to ``"unmatched"`` for unrouted requests.
    """
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None)
    if isinstance(path_format, str):
        return path_format
    return "unmatched"


@app.middleware("http")
async def _record_http_metrics(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Record per-request latency and a status-labeled request counter."""
    start = time.perf_counter()
    response = await call_next(request)
    path = _route_label(request)
    # /metrics itself is excluded so a scrape doesn't inflate its own counters.
    if path != "/metrics":
        http_request_duration_seconds.labels(method=request.method, path=path).observe(
            time.perf_counter() - start
        )
        http_requests_total.labels(
            method=request.method, path=path, status=str(response.status_code)
        ).inc()
    return response


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
app.include_router(router=artifact.router)
app.include_router(router=auth.router)
app.include_router(router=channel.router)
app.include_router(router=connection.router)
app.include_router(router=user.router)
app.include_router(router=workflow.router)
app.include_router(router=workflow_template.router)
app.include_router(router=node.router)
app.include_router(router=postgres_connection.router)
app.include_router(router=state.router)
app.include_router(router=edge.router)
app.include_router(router=email_account.router)
app.include_router(router=execution.router)
app.include_router(router=llm_provider.router)
app.include_router(router=mcp_server.router)
app.include_router(router=telegram_bot.router)
app.include_router(router=vector.router)
app.include_router(router=usage.router)
app.include_router(router=metrics.router)
app.include_router(router=web_chat.router)
app.include_router(router=webhook.router)
