"""Unified connection dependency providers."""

from usecases import ConnectionUsecase


def get_connection_usecase() -> ConnectionUsecase:
    """Return the unified connection use case."""
    return ConnectionUsecase()
