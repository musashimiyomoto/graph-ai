"""Graph AI Backend entrypoint."""

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

app = FastAPI(title="Graph AI Backend")


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
