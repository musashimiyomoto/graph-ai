"""LLM provider use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import LLMProviderRepository
from exceptions import BlockedURLError, LLMProviderNotFoundError
from llm import create_llm_client
from schemas import (
    LLMProviderCreate,
    LLMProviderModelResponse,
    LLMProviderResponse,
    LLMProviderUpdate,
)
from utils.encryption import decrypt, encrypt
from utils.network import blocked_url_reason


async def _ensure_allowed_base_url(base_url: str) -> None:
    """Reject provider base URLs that resolve to disallowed hosts.

    Providers may legitimately be self-hosted (e.g. Ollama on a private host), so
    loopback/private ranges are allowed; link-local (incl. cloud metadata),
    multicast, reserved, and unspecified addresses are blocked.

    Args:
        base_url: The provider base URL.

    Raises:
        BlockedURLError: If the URL resolves to a disallowed address.

    """
    reason = await blocked_url_reason(base_url, allow_private=True)
    if reason is not None:
        raise BlockedURLError(message=reason)


class LLMProviderUsecase:
    """LLM provider business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._llm_provider_repository = LLMProviderRepository()

    async def create_llm_provider(
        self,
        session: AsyncSession,
        user_id: int,
        data: LLMProviderCreate,
    ) -> LLMProviderResponse:
        """Create a new LLM provider.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The provider creation fields.

        Returns:
            The created LLM provider.

        """
        payload = data.model_dump(mode="json")
        await _ensure_allowed_base_url(payload["base_url"])
        if payload.get("api_key") is not None:
            payload["api_key"] = encrypt(payload["api_key"])

        return LLMProviderResponse.model_validate(
            await self._llm_provider_repository.create(
                session=session,
                data={**payload, "user_id": user_id},
            )
        )

    async def get_llm_providers(
        self, session: AsyncSession, user_id: int
    ) -> list[LLMProviderResponse]:
        """List LLM providers for a user.

        Args:
            session: The session.
            user_id: The owner user ID.

        Returns:
            The list of LLM providers.

        """
        return [
            LLMProviderResponse.model_validate(llm_provider)
            for llm_provider in await self._llm_provider_repository.get_all(
                session=session, user_id=user_id
            )
        ]

    async def get_llm_provider(
        self, session: AsyncSession, provider_id: int, user_id: int
    ) -> LLMProviderResponse:
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

        return LLMProviderResponse.model_validate(provider)

    async def update_llm_provider(
        self,
        session: AsyncSession,
        provider_id: int,
        user_id: int,
        data: LLMProviderUpdate,
    ) -> LLMProviderResponse:
        """Update an LLM provider by ID.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.
            data: The fields to update.

        Returns:
            The updated LLM provider.

        Raises:
            LLMProviderNotFoundError: If the LLM provider is not found.

        """
        llm_provider = await self.get_llm_provider(
            session=session, provider_id=provider_id, user_id=user_id
        )

        update_data = data.model_dump(exclude_none=True, mode="json")
        if not update_data:
            return llm_provider

        if update_data.get("base_url"):
            await _ensure_allowed_base_url(update_data["base_url"])

        if "api_key" in update_data:
            update_data["api_key"] = encrypt(update_data["api_key"])

        llm_provider = await self._llm_provider_repository.update_by(
            session=session, data=update_data, id=provider_id
        )
        if not llm_provider:
            raise LLMProviderNotFoundError

        return LLMProviderResponse.model_validate(llm_provider)

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
    ) -> list[LLMProviderModelResponse]:
        """Fetch available models from an LLM provider.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.

        Returns:
            A list of model metadata.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            LLMProviderConfigError: If the provider configuration is invalid.
            LLMProviderConnectionError: If the provider is unreachable.
            UnsupportedLLMProviderError: If the provider type is unsupported.

        """
        llm_provider = await self._llm_provider_repository.get_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not llm_provider:
            raise LLMProviderNotFoundError

        await _ensure_allowed_base_url(llm_provider.base_url)
        api_key = decrypt(llm_provider.api_key) if llm_provider.api_key else None

        return await create_llm_client(
            llm_provider=LLMProviderResponse.model_validate(llm_provider),
            api_key=api_key,
        ).list_models()
