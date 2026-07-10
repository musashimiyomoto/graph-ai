"""LLM provider use case implementation."""

from arq import ArqRedis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from constants import DEFAULT_TIMEOUT
from db.repositories import LLMProviderRepository
from enums import LLMProviderType
from exceptions import (
    BlockedURLError,
    LLMProviderAlreadyExistsError,
    LLMProviderNotFoundError,
    UnsupportedLLMProviderError,
)
from llm import create_llm_client
from llm.ollama import OllamaClient
from schemas import (
    LLMProviderCreate,
    LLMProviderModelResponse,
    LLMProviderResponse,
    LLMProviderUpdate,
    OllamaModelPullResponse,
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

        Raises:
            LLMProviderAlreadyExistsError: If the user already has a provider
                with this name.

        """
        payload = data.model_dump(mode="json")
        await _ensure_allowed_base_url(payload["base_url"])
        if payload.get("api_key") is not None:
            payload["api_key"] = encrypt(payload["api_key"])

        try:
            created = await self._llm_provider_repository.create(
                session=session,
                data={**payload, "user_id": user_id},
            )
        except IntegrityError as exc:
            await session.rollback()
            raise LLMProviderAlreadyExistsError from exc

        await session.commit()
        return LLMProviderResponse.model_validate(created)

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
            LLMProviderAlreadyExistsError: If the user already has a provider
                with this name.

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

        try:
            llm_provider = await self._llm_provider_repository.update_by(
                session=session, data=update_data, id=provider_id
            )
        except IntegrityError as exc:
            await session.rollback()
            raise LLMProviderAlreadyExistsError from exc
        if not llm_provider:
            raise LLMProviderNotFoundError

        await session.commit()
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
        await session.commit()

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

    async def _require_ollama_base_url(
        self, session: AsyncSession, provider_id: int, user_id: int
    ) -> str:
        """Return an owned Ollama provider's validated base URL.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.

        Returns:
            The provider's base URL.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            UnsupportedLLMProviderError: If the provider is not an Ollama one
                (only Ollama supports pulling/deleting models).
            BlockedURLError: If the base URL resolves to a disallowed host.

        """
        provider = await self._llm_provider_repository.get_by(
            session=session, id=provider_id, user_id=user_id
        )
        if not provider:
            raise LLMProviderNotFoundError
        if provider.type is not LLMProviderType.OLLAMA:
            raise UnsupportedLLMProviderError(
                message="Only Ollama providers support managing models"
            )
        await _ensure_allowed_base_url(provider.base_url)
        return provider.base_url

    async def start_model_pull(
        self,
        session: AsyncSession,
        provider_id: int,
        user_id: int,
        model: str,
        pool: ArqRedis,
    ) -> OllamaModelPullResponse:
        """Queue a background pull of an Ollama model.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.
            model: The model name/tag to pull.
            pool: The ARQ pool to enqueue the job on.

        Returns:
            The deterministic job id (dedup key) and the model being pulled.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            UnsupportedLLMProviderError: If the provider is not an Ollama one.
            BlockedURLError: If the base URL resolves to a disallowed host.

        """
        base_url = await self._require_ollama_base_url(
            session=session, provider_id=provider_id, user_id=user_id
        )
        # Deterministic id both dedups concurrent identical pulls and lets the
        # client subscribe to the progress channel it already knows.
        job_id = f"ollama-pull:{provider_id}:{model}"
        await pool.enqueue_job(
            "pull_ollama_model_task", base_url, model, _job_id=job_id
        )
        return OllamaModelPullResponse(job_id=job_id, model=model)

    async def delete_model(
        self, session: AsyncSession, provider_id: int, user_id: int, model: str
    ) -> None:
        """Delete a model from an Ollama provider.

        Args:
            session: The session.
            provider_id: The provider ID.
            user_id: The owner user ID.
            model: The model name/tag to delete.

        Raises:
            LLMProviderNotFoundError: If the provider is not found.
            UnsupportedLLMProviderError: If the provider is not an Ollama one.
            BlockedURLError: If the base URL resolves to a disallowed host.
            LLMProviderConnectionError: If the provider is unreachable.

        """
        base_url = await self._require_ollama_base_url(
            session=session, provider_id=provider_id, user_id=user_id
        )
        await OllamaClient(base_url=base_url, timeout=DEFAULT_TIMEOUT).delete_model(
            model
        )
