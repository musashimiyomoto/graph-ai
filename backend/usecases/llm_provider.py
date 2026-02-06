"""LLM provider use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import LLMProviderNotFoundError
from models import LLMProvider
from repositories import LLMProviderRepository, UserRepository


class LLMProviderUsecase:
    """LLM provider business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._provider_repository = LLMProviderRepository()
        self._user_repository = UserRepository()

    async def create_provider(
        self,
        session: AsyncSession,
        user_id: int,
        **kwargs: object,
    ) -> LLMProvider:
        """Create a new LLM provider.

        Args:
            session: The session.
            user_id: The owner user ID.
            **kwargs: The provider creation fields.

        Returns:
            The created LLM provider.

        Raises:
            UserNotFoundError: If the owner user is not found.

        """
        return await self._provider_repository.create(
            session=session,
            data={**kwargs, "user_id": user_id},
        )

    async def get_providers(
        self, session: AsyncSession, user_id: int
    ) -> list[LLMProvider]:
        """List LLM providers for a user.

        Args:
            session: The session.
            user_id: The owner user ID.

        Returns:
            The list of LLM providers.

        """
        return await self._provider_repository.get_all(session=session, user_id=user_id)

    async def get_provider(
        self, session: AsyncSession, provider_id: int, user_id: int
    ) -> LLMProvider:
        """Fetch an LLM provider by ID.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.

        Returns:
            The LLM provider.

        Raises:
            LLMProviderNotFoundError: If the LLM provider is not found.

        """
        provider = await self._provider_repository.get_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not provider:
            raise LLMProviderNotFoundError

        return provider

    async def update_provider(
        self, session: AsyncSession, provider_id: int, user_id: int, **kwargs: object
    ) -> LLMProvider:
        """Update an LLM provider by ID.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.
            **kwargs: The fields to update.

        Returns:
            The updated LLM provider.

        Raises:
            LLMProviderNotFoundError: If the LLM provider is not found.

        """
        provider = await self.get_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return provider

        provider = await self._provider_repository.update_by(
            session=session, data=update_data, id=provider_id
        )
        if not provider:
            raise LLMProviderNotFoundError

        return provider

    async def delete_provider(
        self, session: AsyncSession, provider_id: int, user_id: int
    ) -> None:
        """Delete an LLM provider by ID.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.

        Raises:
            LLMProviderNotFoundError: If the LLM provider is not found.

        """
        deleted = await self._provider_repository.delete_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not deleted:
            raise LLMProviderNotFoundError
