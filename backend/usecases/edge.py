"""Edge use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import EdgeRepository, NodeRepository, WorkflowRepository
from exceptions import (
    EdgeNodeMismatchError,
    EdgeNotFoundError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
from schemas import EdgeCreate, EdgeResponse, EdgeUpdate


class EdgeUsecase:
    """Edge business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._edge_repository = EdgeRepository()
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()

    async def create_edge(
        self,
        session: AsyncSession,
        user_id: int,
        data: EdgeCreate,
    ) -> EdgeResponse:
        """Create an edge between nodes in a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The edge creation fields.

        Returns:
            The created edge.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            NodeNotFoundError: If the source or target node is not found.
            EdgeNodeMismatchError: If the nodes do not belong to the workflow.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=data.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        source_node = await self._node_repository.get_by(
            session=session, id=data.source_node_id
        )
        if not source_node:
            raise NodeNotFoundError

        target_node = await self._node_repository.get_by(
            session=session, id=data.target_node_id
        )
        if not target_node:
            raise NodeNotFoundError

        if source_node.workflow_id != data.workflow_id:
            raise EdgeNodeMismatchError
        if target_node.workflow_id != data.workflow_id:
            raise EdgeNodeMismatchError

        return EdgeResponse.model_validate(
            await self._edge_repository.create(session=session, data=data.model_dump())
        )

    async def get_edges(
        self, session: AsyncSession, user_id: int, workflow_id: int
    ) -> list[EdgeResponse]:
        """List edges for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.

        Returns:
            The list of edges.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        edges = await self._edge_repository.get_all(
            session=session, workflow_id=workflow_id
        )
        return [EdgeResponse.model_validate(edge) for edge in edges]

    async def get_edge(
        self, session: AsyncSession, edge_id: int, user_id: int
    ) -> EdgeResponse:
        """Fetch an edge by ID.

        Args:
            session: The session.
            edge_id: The edge ID.
            user_id: The owner user ID.

        Returns:
            The edge.

        Raises:
            EdgeNotFoundError: If the edge is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        edge = await self._edge_repository.get_by(session=session, id=edge_id)
        if not edge:
            raise EdgeNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=edge.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return EdgeResponse.model_validate(edge)

    async def update_edge(
        self,
        session: AsyncSession,
        edge_id: int,
        user_id: int,
        data: EdgeUpdate,
    ) -> EdgeResponse:
        """Update an edge by ID.

        Args:
            session: The session.
            edge_id: The edge ID.
            user_id: The owner user ID.
            data: The fields to update.

        Returns:
            The updated edge.

        Raises:
            EdgeNotFoundError: If the edge is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        edge = await self.get_edge(session=session, edge_id=edge_id, user_id=user_id)

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return edge

        source_node_id = update_data.get("source_node_id", edge.source_node_id)
        target_node_id = update_data.get("target_node_id", edge.target_node_id)

        source_node = await self._node_repository.get_by(
            session=session, id=source_node_id
        )
        if not source_node:
            raise NodeNotFoundError

        target_node = await self._node_repository.get_by(
            session=session, id=target_node_id
        )
        if not target_node:
            raise NodeNotFoundError

        if (
            source_node.workflow_id != edge.workflow_id
            or target_node.workflow_id != edge.workflow_id
        ):
            raise EdgeNodeMismatchError

        edge = await self._edge_repository.update_by(
            session=session,
            data=update_data,
            id=edge_id,
        )
        if not edge:
            raise EdgeNotFoundError

        return EdgeResponse.model_validate(edge)

    async def delete_edge(
        self, session: AsyncSession, edge_id: int, user_id: int
    ) -> None:
        """Delete an edge by ID.

        Args:
            session: The session.
            edge_id: The edge ID.
            user_id: The owner user ID.

        Raises:
            EdgeNotFoundError: If the edge is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        await self.get_edge(session=session, edge_id=edge_id, user_id=user_id)

        deleted = await self._edge_repository.delete_by(session=session, id=edge_id)
        if not deleted:
            raise EdgeNotFoundError
