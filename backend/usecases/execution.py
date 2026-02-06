"""Execution use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import ExecutionNotFoundError, WorkflowNotFoundError
from models import Execution
from repositories import ExecutionRepository, WorkflowRepository


class ExecutionUsecase:
    """Execution business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._execution_repository = ExecutionRepository()
        self._workflow_repository = WorkflowRepository()

    async def create_execution(
        self,
        session: AsyncSession,
        user_id: int,
        workflow_id: int,
        input_data: dict | None = None,
    ) -> Execution:
        """Create an execution for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.
            input_data: The execution input data.

        Returns:
            The created execution.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._execution_repository.create(
            session=session,
            data={
                "workflow_id": workflow_id,
                "input_data": input_data,
            },
        )

    async def get_executions(
        self, session: AsyncSession, user_id: int, workflow_id: int
    ) -> list[Execution]:
        """List executions for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.

        Returns:
            The list of executions.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._execution_repository.get_all(
            session=session, workflow_id=workflow_id
        )

    async def get_execution(
        self, session: AsyncSession, execution_id: int, user_id: int
    ) -> Execution:
        """Fetch an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.
            user_id: The owner user ID.

        Returns:
            The execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if not execution:
            raise ExecutionNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=execution.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return execution
