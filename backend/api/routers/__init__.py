"""API router package."""

from api.routers import (
    auth,
    edge,
    execution,
    health,
    llm_provider,
    mcp_server,
    node,
    postgres_connection,
    telegram_bot,
    user,
    vector,
    workflow,
    workflow_template,
)

__all__ = [
    "auth",
    "edge",
    "execution",
    "health",
    "llm_provider",
    "mcp_server",
    "node",
    "postgres_connection",
    "telegram_bot",
    "user",
    "vector",
    "workflow",
    "workflow_template",
]
