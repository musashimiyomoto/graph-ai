"""Node use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeType
from exceptions import NodeNotFoundError, WorkflowNotFoundError
from models import Node
from repositories import NodeRepository, WorkflowRepository


class NodeUsecase:
    """Node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()

    async def create_node(
        self,
        session: AsyncSession,
        workflow_id: int,
        type: NodeType,  # noqa: A002
        position_x: float = 0.0,
        position_y: float = 0.0,
    ) -> Node:
        """Create a node within a workflow.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            type: The node type.
            position_x: The X position on canvas.
            position_y: The Y position on canvas.

        Returns:
            The created node.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._node_repository.create(
            session=session,
            data={
                "workflow_id": workflow_id,
                "type": type,
                "position_x": position_x,
                "position_y": position_y,
            },
        )

    async def get_nodes(
        self, session: AsyncSession, workflow_id: int | None = None
    ) -> list[Node]:
        """List nodes, optionally filtered by workflow.

        Args:
            session: The session.
            workflow_id: The workflow ID.

        Returns:
            The list of nodes.

        """
        filters = {"workflow_id": workflow_id} if workflow_id else {}
        return await self._node_repository.get_all(session=session, **filters)

    async def get_node(self, session: AsyncSession, node_id: int) -> Node:
        """Fetch a node by ID.

        Args:
            session: The session.
            node_id: The node ID.

        Returns:
            The node.

        Raises:
            NodeNotFoundError: If the node is not found.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError
        return node

    async def update_node(
        self, session: AsyncSession, node_id: int, **kwargs: object
    ) -> Node:
        """Update a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            **kwargs: The fields to update.

        Returns:
            The updated node.

        Raises:
            NodeNotFoundError: If the node is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_node(session=session, node_id=node_id)

        node = await self._node_repository.update_by(
            session=session,
            data=update_data,
            id=node_id,
        )
        if not node:
            raise NodeNotFoundError
        return node

    async def delete_node(self, session: AsyncSession, node_id: int) -> None:
        """Delete a node by ID.

        Args:
            session: The session.
            node_id: The node ID.

        Raises:
            NodeNotFoundError: If the node is not found.

        """
        deleted = await self._node_repository.delete_by(session=session, id=node_id)
        if not deleted:
            raise NodeNotFoundError
