"""Input node use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums import InputFormat, NodeType
from exceptions import NodeConfigExistsError, NodeNotFoundError, NodeTypeMismatchError
from models import InputNode
from repositories import InputNodeRepository, NodeRepository


class InputNodeUsecase:
    """Input node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._input_repository = InputNodeRepository()
        self._node_repository = NodeRepository()

    async def create_input_node(
        self,
        session: AsyncSession,
        node_id: int,
        format: InputFormat = InputFormat.TEXT,  # noqa: A002
    ) -> InputNode:
        """Create an input node configuration.

        Args:
            session: The session.
            node_id: The node ID.
            format: The input format.

        Returns:
            The created input node.

        Raises:
            NodeNotFoundError: If the node is not found.
            NodeTypeMismatchError: If the node type is not INPUT.
            NodeConfigExistsError: If config already exists.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError
        if node.type != NodeType.INPUT:
            raise NodeTypeMismatchError

        existing = await self._input_repository.get_by(session=session, node_id=node_id)
        if existing:
            raise NodeConfigExistsError

        return await self._input_repository.create(
            session=session,
            data={"node_id": node_id, "format": format},
        )

    async def get_input_node(self, session: AsyncSession, node_id: int) -> InputNode:
        """Fetch an input node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Returns:
            The input node.

        Raises:
            NodeNotFoundError: If the input node is not found.

        """
        input_node = await self._input_repository.get_by(
            session=session, node_id=node_id
        )
        if not input_node:
            raise NodeNotFoundError
        return input_node

    async def update_input_node(
        self, session: AsyncSession, node_id: int, **kwargs: object
    ) -> InputNode:
        """Update an input node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.
            **kwargs: The fields to update.

        Returns:
            The updated input node.

        Raises:
            NodeNotFoundError: If the input node is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_input_node(session=session, node_id=node_id)

        input_node = await self._input_repository.update_by(
            session=session,
            data=update_data,
            node_id=node_id,
        )
        if not input_node:
            raise NodeNotFoundError
        return input_node

    async def delete_input_node(self, session: AsyncSession, node_id: int) -> None:
        """Delete an input node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Raises:
            NodeNotFoundError: If the input node is not found.

        """
        deleted = await self._input_repository.delete_by(
            session=session, node_id=node_id
        )
        if not deleted:
            raise NodeNotFoundError
