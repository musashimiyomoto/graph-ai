"""Output node use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeType, OutputFormat
from exceptions import NodeConfigExistsError, NodeNotFoundError, NodeTypeMismatchError
from models import OutputNode
from repositories import NodeRepository, OutputNodeRepository


class OutputNodeUsecase:
    """Output node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._output_repository = OutputNodeRepository()
        self._node_repository = NodeRepository()

    async def create_output_node(
        self,
        session: AsyncSession,
        node_id: int,
        format: OutputFormat = OutputFormat.TEXT,  # noqa: A002
    ) -> OutputNode:
        """Create an output node configuration.

        Args:
            session: The session.
            node_id: The node ID.
            format: The output format.

        Returns:
            The created output node.

        Raises:
            NodeNotFoundError: If the node is not found.
            NodeTypeMismatchError: If the node type is not OUTPUT.
            NodeConfigExistsError: If config already exists.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError
        if node.type != NodeType.OUTPUT:
            raise NodeTypeMismatchError

        existing = await self._output_repository.get_by(
            session=session, node_id=node_id
        )
        if existing:
            raise NodeConfigExistsError

        return await self._output_repository.create(
            session=session,
            data={"node_id": node_id, "format": format},
        )

    async def get_output_node(self, session: AsyncSession, node_id: int) -> OutputNode:
        """Fetch an output node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Returns:
            The output node.

        Raises:
            NodeNotFoundError: If the output node is not found.

        """
        output_node = await self._output_repository.get_by(
            session=session, node_id=node_id
        )
        if not output_node:
            raise NodeNotFoundError
        return output_node

    async def update_output_node(
        self, session: AsyncSession, node_id: int, **kwargs: object
    ) -> OutputNode:
        """Update an output node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.
            **kwargs: The fields to update.

        Returns:
            The updated output node.

        Raises:
            NodeNotFoundError: If the output node is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_output_node(session=session, node_id=node_id)

        output_node = await self._output_repository.update_by(
            session=session,
            data=update_data,
            node_id=node_id,
        )
        if not output_node:
            raise NodeNotFoundError
        return output_node

    async def delete_output_node(self, session: AsyncSession, node_id: int) -> None:
        """Delete an output node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Raises:
            NodeNotFoundError: If the output node is not found.

        """
        deleted = await self._output_repository.delete_by(
            session=session, node_id=node_id
        )
        if not deleted:
            raise NodeNotFoundError
