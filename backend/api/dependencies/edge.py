"""Edge dependency providers."""

from usecases import EdgeUsecase


def get_edge_usecase() -> EdgeUsecase:
    """Get the edge usecase.

    Returns:
        The edge usecase.

    """
    return EdgeUsecase()
