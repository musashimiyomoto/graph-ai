"""Input node dependency providers."""

from usecases import InputNodeUsecase


def get_input_node_usecase() -> InputNodeUsecase:
    """Get the input node usecase.

    Returns:
        The input node usecase.

    """
    return InputNodeUsecase()
