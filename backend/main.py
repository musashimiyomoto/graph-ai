"""Graph AI Backend entrypoint."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from exceptions import BaseError
from routers import (
    auth,
    edge,
    execution,
    health,
    llm_provider,
    node,
    user,
    workflow,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Graph AI Backend")


@app.exception_handler(BaseError)
async def handle_base_error(_: Request, exc: BaseError) -> JSONResponse:
    """Handle domain errors as JSON responses.

    Args:
        _: The incoming request.
        exc: The domain error.

    Returns:
        A JSON response with the error detail.

    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(auth.router)
app.include_router(health.router)
app.include_router(user.router)
app.include_router(workflow.router)
app.include_router(node.router)
app.include_router(edge.router)
app.include_router(execution.router)
app.include_router(llm_provider.router)
