"""Prefect flow entrypoint for workflow execution."""

from prefect import flow

from constants import EXECUTION_FLOW_NAME
from sessions import async_session
from usecases import ExecutionUsecase


@flow(name=EXECUTION_FLOW_NAME)
async def run_workflow_execution(execution_id: int) -> None:
    """Run one workflow execution and persist resulting status.

    Args:
        execution_id: Execution ID.

    Raises:
        Exception: If execution logic fails.

    """
    async with async_session() as session:
        await ExecutionUsecase().execute_and_finalize(
            session=session,
            execution_id=execution_id,
        )
