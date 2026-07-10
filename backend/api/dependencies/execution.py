"""Execution dependency providers."""

from typing import Annotated

from fastapi import Query

from enums import ExecutionSource
from usecases import ExecutionListFilter, ExecutionUsecase


def get_execution_usecase() -> ExecutionUsecase:
    """Get the execution usecase.

    Returns:
        The execution usecase.

    """
    return ExecutionUsecase()


def get_execution_list_filter(
    workflow_id: Annotated[int, Query(gt=0)],
    source: Annotated[
        ExecutionSource | None,
        Query(description="Filter to executions triggered this way"),
    ] = None,
) -> ExecutionListFilter:
    """Build the workflow/source filter for listing executions."""
    return ExecutionListFilter(workflow_id=workflow_id, source=source)
