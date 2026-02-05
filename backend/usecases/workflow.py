"""Workflow use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import UserNotFoundError, WorkflowNotFoundError
from models import Workflow
from repositories import UserRepository, WorkflowRepository


class WorkflowUsecase:
    """Workflow business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._workflow_repository = WorkflowRepository()
        self._user_repository = UserRepository()

    async def create_workflow(
        self, session: AsyncSession, owner_id: int, name: str
    ) -> Workflow:
        """Create a workflow for a user.

        Args:
            session: The session.
            owner_id: The owner user ID.
            name: The workflow name.

        Returns:
            The created workflow.

        Raises:
            UserNotFoundError: If the owner user is not found.

        """
        owner = await self._user_repository.get_by(session=session, id=owner_id)
        if not owner:
            raise UserNotFoundError

        return await self._workflow_repository.create(
            session=session,
            data={"owner_id": owner_id, "name": name},
        )

    async def get_workflows(
        self, session: AsyncSession, owner_id: int | None = None
    ) -> list[Workflow]:
        """List workflows, optionally filtered by owner.

        Args:
            session: The session.
            owner_id: The owner user ID.

        Returns:
            The list of workflows.

        """
        filters = {"owner_id": owner_id} if owner_id else {}
        return await self._workflow_repository.get_all(session=session, **filters)

    async def get_workflow(self, session: AsyncSession, workflow_id: int) -> Workflow:
        """Fetch a workflow by ID.

        Args:
            session: The session.
            workflow_id: The workflow ID.

        Returns:
            The workflow.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id
        )
        if not workflow:
            raise WorkflowNotFoundError
        return workflow

    async def update_workflow(
        self, session: AsyncSession, workflow_id: int, **kwargs: object
    ) -> Workflow:
        """Update a workflow by ID.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            **kwargs: The fields to update.

        Returns:
            The updated workflow.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_workflow(session=session, workflow_id=workflow_id)

        workflow = await self._workflow_repository.update_by(
            session=session,
            data=update_data,
            id=workflow_id,
        )
        if not workflow:
            raise WorkflowNotFoundError
        return workflow

    async def delete_workflow(self, session: AsyncSession, workflow_id: int) -> None:
        """Delete a workflow by ID.

        Args:
            session: The session.
            workflow_id: The workflow ID.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        deleted = await self._workflow_repository.delete_by(
            session=session, id=workflow_id
        )
        if not deleted:
            raise WorkflowNotFoundError
