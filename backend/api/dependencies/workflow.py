"""Workflow dependency providers."""

from usecases import WorkflowTransferUsecase, WorkflowUsecase


def get_workflow_usecase() -> WorkflowUsecase:
    """Get the workflow usecase.

    Returns:
        The workflow usecase.

    """
    return WorkflowUsecase()


def get_workflow_transfer_usecase() -> WorkflowTransferUsecase:
    """Get the workflow transfer usecase.

    Returns:
        The workflow transfer usecase.

    """
    return WorkflowTransferUsecase()
