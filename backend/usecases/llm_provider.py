"""LLM provider use case implementation."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import LLMProviderConnectionError, LLMProviderNotFoundError
from integrations import LLMClientFactory
from models import LLMProvider
from repositories import LLMProviderRepository
from schemas import LLMModel


class LLMProviderUsecase:
    """LLM provider business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._llm_provider_repository = LLMProviderRepository()
        self._llm_client_factory = LLMClientFactory()

    async def create_llm_provider(
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

        """
        return await self._llm_provider_repository.create(
            session=session,
            data={**kwargs, "user_id": user_id},
        )

    async def get_llm_providers(
        self, session: AsyncSession, user_id: int
    ) -> list[LLMProvider]:
        """List LLM providers for a user.

        Args:
            session: The session.
            user_id: The owner user ID.

        Returns:
            The list of LLM providers.

        """
        return await self._llm_provider_repository.get_all(
            session=session, user_id=user_id
        )

    async def get_llm_provider(
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
            LLMProviderConfigError: If the provider configuration is invalid.

        """
        provider = await self._llm_provider_repository.get_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not provider:
            raise LLMProviderNotFoundError

        return provider

    async def update_llm_provider(
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
        provider = await self.get_llm_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        update_data = {k: v for k, v in kwargs.items() if v is not None}

        if not update_data:
            return provider

        provider = await self._llm_provider_repository.update_by(
            session=session, data=update_data, id=provider_id
        )
        if not provider:
            raise LLMProviderNotFoundError

        return provider

    async def delete_llm_provider(
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
        deleted = await self._llm_provider_repository.delete_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not deleted:
            raise LLMProviderNotFoundError

    async def get_models(
        self, session: AsyncSession, provider_id: int, user_id: int
    ) -> list[LLMModel]:
        """Fetch available models from an LLM provider.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.

        Returns:
            A list of model metadata.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            LLMProviderConnectionError: If the provider is unreachable.
            UnsupportedLLMProviderError: If the provider type is unsupported.

        """
        llm_provider = await self.get_llm_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        try:
            return await self._llm_client_factory.get_client(
                llm_provider=llm_provider
            ).list_models()
        except httpx.TimeoutException as exc:
            raise LLMProviderConnectionError(
                message="LLM provider request timed out while listing models"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            message = f"LLM provider returned {exc.response.status_code}"
            if detail:
                message = f"{message}: {detail[:300]}"
            raise LLMProviderConnectionError(message=message) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderConnectionError from exc
