"""Workflow dependency providers."""

from usecases import WorkflowUsecase


def get_workflow_usecase() -> WorkflowUsecase:
    """Get the workflow usecase.

    Returns:
        The workflow usecase.

    """
    return WorkflowUsecase()
