"""Output node dependency providers."""

from usecases import OutputNodeUsecase


def get_output_node_usecase() -> OutputNodeUsecase:
    """Get the output node usecase.

    Returns:
        The output node usecase.

    """
    return OutputNodeUsecase()
