"""Node use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeDataSpec, NodeType
from exceptions import (
    NodeDataValidationError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
from models import Node
from repositories import NodeRepository, WorkflowRepository


class NodeUsecase:
    """Node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()

    def get_node_fields(self, node_type: NodeType) -> tuple[dict]:
        """Return field definitions, optionally filtered by node type.

        Args:
            node_type: Node type to filter by.

        Returns:
            A list of field definitions.

        """
        return NodeDataSpec[node_type.name].value

    def _validate_node_data(self, node_type: NodeType, data: dict) -> dict:
        """Validate node data for a specific node type.

        Args:
            node_type: The node type.
            data: The raw node data.

        Returns:
            The sanitized node data.

        Raises:
            NodeDataValidationError: If the data is invalid.

        """
        try:
            return NodeDataSpec[node_type.name].validate(data=data)
        except ValueError as exc:
            raise NodeDataValidationError(message=str(exc)) from exc

    async def create_node(
        self,
        session: AsyncSession,
        user_id: int,
        **kwargs: object,
    ) -> Node:
        """Create a node within a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            **kwargs: The node creation fields.

        Returns:
            The created node.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=kwargs["workflow_id"], owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        node_type = kwargs.get("type")
        if not isinstance(node_type, NodeType):
            raise NodeDataValidationError(message="Node type is required.")

        raw_data = kwargs.get("data", {})
        if not isinstance(raw_data, dict):
            raise NodeDataValidationError(message="Node data must be an object.")

        kwargs["data"] = self._validate_node_data(node_type=node_type, data=raw_data)

        return await self._node_repository.create(
            session=session,
            data=kwargs,
        )

    async def get_nodes(
        self, session: AsyncSession, user_id: int, workflow_id: int
    ) -> list[Node]:
        """List nodes for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.

        Returns:
            The list of nodes.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._node_repository.get_all(
            session=session, workflow_id=workflow_id
        )

    async def get_node(self, session: AsyncSession, node_id: int, user_id: int) -> Node:
        """Fetch a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.

        Returns:
            The node.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=node.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return node

    async def update_node(
        self, session: AsyncSession, node_id: int, user_id: int, **kwargs: object
    ) -> Node:
        """Update a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.
            **kwargs: The fields to update.

        Returns:
            The updated node.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        node = await self.get_node(session=session, node_id=node_id, user_id=user_id)

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return node

        incoming_data = update_data.get("data", {})
        if not isinstance(incoming_data, dict):
            raise NodeDataValidationError(message="Node data must be an object.")

        update_data["data"] = self._validate_node_data(
            node_type=node.type, data=node.data | incoming_data
        )

        node = await self._node_repository.update_by(
            session=session,
            data=update_data,
            id=node_id,
        )
        if not node:
            raise NodeNotFoundError

        return node

    async def delete_node(
        self, session: AsyncSession, node_id: int, user_id: int
    ) -> None:
        """Delete a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        await self.get_node(session=session, node_id=node_id, user_id=user_id)

        deleted = await self._node_repository.delete_by(session=session, id=node_id)
        if not deleted:
            raise NodeNotFoundError
