"""Execution dependency providers."""

from usecases import ExecutionUsecase


def get_execution_usecase() -> ExecutionUsecase:
    """Get the execution usecase.

    Returns:
        The execution usecase.

    """
    return ExecutionUsecase()
