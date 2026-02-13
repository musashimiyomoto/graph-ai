"""Health dependency providers."""

from usecases import HealthUsecase


def get_health_usecase() -> HealthUsecase:
    """Get the health usecase.

    Returns:
        The health usecase.

    """
    return HealthUsecase()
