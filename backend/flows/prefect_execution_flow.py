"""Prefect flow entrypoint for workflow execution."""

from prefect import flow

import usecases.execution as execution_usecase
from constants import EXECUTION_FLOW_NAME
from sessions import async_session

FLOW_NAME = EXECUTION_FLOW_NAME


@flow(name=FLOW_NAME)
async def run_workflow_execution(execution_id: int) -> None:
    """Run one workflow execution and persist resulting status.

    Args:
        execution_id: Execution ID.

    Raises:
        Exception: If execution logic fails.

    """
    usecase = execution_usecase.ExecutionUsecase()
    async with async_session() as session:
        await usecase.execute_and_finalize(
            session=session,
            execution_id=execution_id,
        )
