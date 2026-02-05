"""Execution use case implementation."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from enums import ExecutionStatus
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
        workflow_id: int,
        input_data: dict | None = None,
        status: ExecutionStatus | None = None,
    ) -> Execution:
        """Create an execution for a workflow.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            input_data: The execution input data.
            status: The execution status.

        Returns:
            The created execution.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        payload: dict[str, object] = {
            "workflow_id": workflow_id,
            "input_data": input_data,
        }
        if status is not None:
            payload["status"] = status

        return await self._execution_repository.create(
            session=session,
            data=payload,
        )

    async def get_executions(
        self, session: AsyncSession, workflow_id: int | None = None
    ) -> list[Execution]:
        """List executions, optionally filtered by workflow.

        Args:
            session: The session.
            workflow_id: The workflow ID.

        Returns:
            The list of executions.

        """
        filters = {"workflow_id": workflow_id} if workflow_id else {}
        return await self._execution_repository.get_all(session=session, **filters)

    async def get_execution(
        self, session: AsyncSession, execution_id: int
    ) -> Execution:
        """Fetch an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.

        Returns:
            The execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.

        """
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if not execution:
            raise ExecutionNotFoundError
        return execution

    async def update_execution(
        self, session: AsyncSession, execution_id: int, **kwargs: object
    ) -> Execution:
        """Update an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.
            **kwargs: The fields to update.

        Returns:
            The updated execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_execution(session=session, execution_id=execution_id)

        status = update_data.get("status")
        if status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED}:
            update_data.setdefault("finished_at", datetime.now(tz=UTC))

        execution = await self._execution_repository.update_by(
            session=session,
            data=update_data,
            id=execution_id,
        )
        if not execution:
            raise ExecutionNotFoundError
        return execution

    async def delete_execution(self, session: AsyncSession, execution_id: int) -> None:
        """Delete an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.

        Raises:
            ExecutionNotFoundError: If the execution is not found.

        """
        deleted = await self._execution_repository.delete_by(
            session=session, id=execution_id
        )
        if not deleted:
            raise ExecutionNotFoundError
