"""LLM provider use case implementation."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from enums import LLMProviderType
from exceptions import (
    LLMProviderConfigError,
    LLMProviderConnectionError,
    LLMProviderNotFoundError,
)
from llms import ChatRequest, ChatResponse, LLMModel, get_llm_client
from models import LLMProvider
from repositories import LLMProviderRepository


class LLMProviderUsecase:
    """LLM provider business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._llm_provider_repository = LLMProviderRepository()

    @staticmethod
    def _validate_provider_config(
        provider_type: LLMProviderType, api_key: str | None
    ) -> None:
        """Validate provider configuration based on type.

        Args:
            provider_type: The LLM provider type.
            api_key: The API key value, if any.

        Raises:
            LLMProviderConfigError: If the provider configuration is invalid.

        """
        if provider_type is LLMProviderType.OLLAMA:
            if api_key is not None:
                raise LLMProviderConfigError(
                    message="Ollama providers must not include an API key."
                )
            return

        if not api_key:
            raise LLMProviderConfigError(message="Cloud providers require an API key.")

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

        Raises:
            LLMProviderConfigError: If the provider configuration is invalid.

        """
        provider_type = kwargs.get("type")
        if not isinstance(provider_type, LLMProviderType):
            raise LLMProviderConfigError(message="LLM provider type is required.")

        api_key_value = kwargs.get("api_key")
        if api_key_value is not None and not isinstance(api_key_value, str):
            raise LLMProviderConfigError(
                message="API key must be a string when provided."
            )
        self._validate_provider_config(
            provider_type=provider_type, api_key=api_key_value
        )

        if provider_type is LLMProviderType.OLLAMA:
            kwargs["api_key"] = None

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

        incoming_type = kwargs.get("type")
        if isinstance(incoming_type, LLMProviderType):
            provider_type = incoming_type
        else:
            provider_type = provider.type
        incoming_api_key = kwargs.get("api_key")
        if incoming_api_key is not None and not isinstance(incoming_api_key, str):
            raise LLMProviderConfigError(
                message="API key must be a string when provided."
            )
        if provider_type is LLMProviderType.OLLAMA:
            if incoming_api_key is not None:
                raise LLMProviderConfigError(
                    message="Ollama providers must not include an API key."
                )
            effective_api_key = None
        else:
            effective_api_key = (
                incoming_api_key if incoming_api_key is not None else provider.api_key
            )

        self._validate_provider_config(
            provider_type=provider_type, api_key=effective_api_key
        )

        if provider_type is LLMProviderType.OLLAMA:
            update_data["api_key"] = None

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
        provider = await self.get_llm_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        try:
            client = get_llm_client(provider=provider)
            return await client.list_models()
        except httpx.HTTPError as exc:
            raise LLMProviderConnectionError from exc

    async def chat(
        self,
        session: AsyncSession,
        provider_id: int,
        user_id: int,
        request: ChatRequest,
    ) -> ChatResponse:
        """Send chat messages to an LLM provider.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.
            request: The chat request payload.

        Returns:
            The chat response payload.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            LLMProviderConnectionError: If the provider is unreachable.
            UnsupportedLLMProviderError: If the provider type is unsupported.

        """
        provider = await self.get_llm_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        try:
            client = get_llm_client(provider=provider)
            return await client.chat(model=request.model, messages=request.messages)
        except httpx.HTTPError as exc:
            raise LLMProviderConnectionError from exc
