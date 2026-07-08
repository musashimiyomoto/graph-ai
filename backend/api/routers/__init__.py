"""API router package."""

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

__all__ = [
    "auth",
    "edge",
    "execution",
    "health",
    "llm_provider",
    "node",
    "telegram_bot",
    "user",
    "vector",
    "workflow",
]
