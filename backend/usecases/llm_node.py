"""LLM node use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeType
from exceptions import (
    LLMProviderNotFoundError,
    NodeConfigExistsError,
    NodeNotFoundError,
    NodeTypeMismatchError,
)
from models import LLMNode
from repositories import LLMNodeRepository, LLMProviderRepository, NodeRepository


class LLMNodeUsecase:
    """LLM node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._llm_repository = LLMNodeRepository()
        self._node_repository = NodeRepository()
        self._provider_repository = LLMProviderRepository()

    async def create_llm_node(  # noqa: PLR0913
        self,
        session: AsyncSession,
        node_id: int,
        llm_provider_id: int,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMNode:
        """Create an LLM node configuration.

        Args:
            session: The session.
            node_id: The node ID.
            llm_provider_id: The LLM provider ID.
            model: The model identifier.
            temperature: The sampling temperature.
            max_tokens: The maximum tokens.

        Returns:
            The created LLM node.

        Raises:
            NodeNotFoundError: If the node is not found.
            NodeTypeMismatchError: If the node type is not LLM.
            LLMProviderNotFoundError: If the provider is not found.
            NodeConfigExistsError: If config already exists.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError
        if node.type != NodeType.LLM:
            raise NodeTypeMismatchError

        provider = await self._provider_repository.get_by(
            session=session, id=llm_provider_id
        )
        if not provider:
            raise LLMProviderNotFoundError

        existing = await self._llm_repository.get_by(session=session, node_id=node_id)
        if existing:
            raise NodeConfigExistsError

        return await self._llm_repository.create(
            session=session,
            data={
                "node_id": node_id,
                "llm_provider_id": llm_provider_id,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

    async def get_llm_node(self, session: AsyncSession, node_id: int) -> LLMNode:
        """Fetch an LLM node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Returns:
            The LLM node.

        Raises:
            NodeNotFoundError: If the LLM node is not found.

        """
        llm_node = await self._llm_repository.get_by(session=session, node_id=node_id)
        if not llm_node:
            raise NodeNotFoundError
        return llm_node

    async def update_llm_node(
        self, session: AsyncSession, node_id: int, **kwargs: object
    ) -> LLMNode:
        """Update an LLM node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.
            **kwargs: The fields to update.

        Returns:
            The updated LLM node.

        Raises:
            NodeNotFoundError: If the LLM node is not found.
            LLMProviderNotFoundError: If the provider is not found.

        """
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return await self.get_llm_node(session=session, node_id=node_id)

        if "llm_provider_id" in update_data:
            provider = await self._provider_repository.get_by(
                session=session, id=update_data["llm_provider_id"]
            )
            if not provider:
                raise LLMProviderNotFoundError

        llm_node = await self._llm_repository.update_by(
            session=session,
            data=update_data,
            node_id=node_id,
        )
        if not llm_node:
            raise NodeNotFoundError
        return llm_node

    async def delete_llm_node(self, session: AsyncSession, node_id: int) -> None:
        """Delete an LLM node configuration by node ID.

        Args:
            session: The session.
            node_id: The node ID.

        Raises:
            NodeNotFoundError: If the LLM node is not found.

        """
        deleted = await self._llm_repository.delete_by(session=session, node_id=node_id)
        if not deleted:
            raise NodeNotFoundError
