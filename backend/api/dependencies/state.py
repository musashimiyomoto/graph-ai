"""Durable state dependency providers."""

from usecases import StateUsecase


def get_state_usecase() -> StateUsecase:
    """Return the durable state use case."""
    return StateUsecase()
