"""Node use case implementation."""

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeType
from exceptions import (
    LLMProviderNotFoundError,
    NodeDataValidationError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
from models import Node
from node_catalog import (
    NodeCatalogItem,
    NodeFieldDataSourceKind,
    get_node_catalog,
    get_node_spec,
    validate_node_data,
)
from repositories import LLMProviderRepository, NodeRepository, WorkflowRepository


class NodeUsecase:
    """Node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()
        self._llm_provider_repository = LLMProviderRepository()

    def get_node_catalog(self) -> tuple[NodeCatalogItem, ...]:
        """Return catalog metadata for all node types.

        Returns:
            A tuple with node catalog entries.

        """
        return get_node_catalog()

    async def _validate_external_references(
        self,
        session: AsyncSession,
        user_id: int,
        node_type: NodeType,
        data: dict[str, Any],
    ) -> None:
        """Validate cross-resource references required by node data.

        Args:
            session: Database session.
            user_id: Owner user ID.
            node_type: Type of node being validated.
            data: Validated node data payload.

        Raises:
            NodeDataValidationError: If reference format is invalid.
            LLMProviderNotFoundError: If a referenced provider is not owned by user.

        """
        spec = get_node_spec(node_type=node_type)

        for field in spec.fields:
            if field.datasource is None or field.name not in data:
                continue

            if field.datasource.kind is NodeFieldDataSourceKind.LLM_PROVIDER:
                provider_id = data[field.name]
                if not isinstance(provider_id, int) or provider_id <= 0:
                    raise NodeDataValidationError(
                        message=(
                            f"Field '{field.name}' must be a positive integer "
                            "provider ID."
                        )
                    )

                provider = await self._llm_provider_repository.get_by(
                    session=session,
                    id=provider_id,
                    user_id=user_id,
                )
                if not provider:
                    raise LLMProviderNotFoundError

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
            LLMProviderNotFoundError: If the LLM provider is not found.
            NodeDataValidationError: If the node data is invalid.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=kwargs["workflow_id"],
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        node_type = kwargs.get("type")
        if not isinstance(node_type, NodeType):
            raise NodeDataValidationError(message="Node type is required.")

        raw_data = kwargs.get("data", {})
        if not isinstance(raw_data, dict):
            raise NodeDataValidationError(message="Node data must be an object.")

        normalized_data = cast("dict[str, Any]", raw_data)
        validated_data = validate_node_data(node_type=node_type, data=normalized_data)
        await self._validate_external_references(
            session=session,
            user_id=user_id,
            node_type=node_type,
            data=validated_data,
        )
        kwargs["data"] = validated_data

        return await self._node_repository.create(session=session, data=kwargs)

    async def get_nodes(
        self,
        session: AsyncSession,
        user_id: int,
        workflow_id: int,
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
            session=session,
            id=workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._node_repository.get_all(
            session=session,
            workflow_id=workflow_id,
        )

    async def get_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
    ) -> Node:
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
            session=session,
            id=node.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        return node

    async def update_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
        **kwargs: object,
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
            NodeDataValidationError: If node data is invalid.

        """
        node = await self.get_node(session=session, node_id=node_id, user_id=user_id)

        update_data = {key: value for key, value in kwargs.items() if value is not None}
        if not update_data:
            return node

        incoming_data = update_data.get("data", {})
        if not isinstance(incoming_data, dict):
            raise NodeDataValidationError(message="Node data must be an object.")

        normalized_data = cast("dict[str, Any]", incoming_data)
        merged_data = node.data | normalized_data
        validated_data = validate_node_data(node_type=node.type, data=merged_data)
        await self._validate_external_references(
            session=session,
            user_id=user_id,
            node_type=node.type,
            data=validated_data,
        )
        update_data["data"] = validated_data

        updated = await self._node_repository.update_by(
            session=session,
            data=update_data,
            id=node_id,
        )
        if not updated:
            raise NodeNotFoundError

        return updated

    async def delete_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
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
