"""LLM integration clients and factory."""

from typing import Protocol

import httpx

from constants import DEFAULT_TIMEOUT
from enums import LLMProviderType
from exceptions import UnsupportedLLMProviderError
from models import LLMProvider
from schemas.llm_provider import ChatMessage, ChatResponse, LLMModel


class BaseLLMClient(Protocol):
    """Interface for LLM provider clients."""

    async def list_models(self) -> list[LLMModel]:
        """List available models from provider."""

    async def chat(self, model: str, messages: list[ChatMessage]) -> ChatResponse:
        """Send chat messages to provider."""


class OllamaClient:
    """Client for the Ollama API."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the Ollama server.
            timeout: Request timeout in seconds.
            transport: Optional transport for testing.

        """
        self._base_url = base_url
        self._timeout = timeout

    async def list_models(self) -> list[LLMModel]:
        """List available models from provider.

        Returns:
            Model metadata list.

        """
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout
        ) as client:
            response = await client.get(url="/api/tags")
            response.raise_for_status()
            payload = response.json()

        return [LLMModel(name=model["name"]) for model in payload.get("models", [])]

    async def chat(self, model: str, messages: list[ChatMessage]) -> ChatResponse:
        """Send chat messages to provider.

        Args:
            model: Model name.
            messages: Chat messages.

        Returns:
            Chat response payload.

        """
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout
        ) as client:
            response = await client.post(
                url="/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": message.role, "content": message.content}
                        for message in messages
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        message_data = data.get("message") or {}

        return ChatResponse(
            model=str(data.get("model", model)),
            message=ChatMessage(
                role=str(message_data.get("role", "")),
                content=str(message_data.get("content", "")),
            ),
            done=bool(data.get("done", False)),
            raw=data,
        )


class LLMClientFactory:
    """Factory for resolving integration client by provider type."""

    def get_client(self, llm_provider: LLMProvider) -> BaseLLMClient:
        """Create an LLM client for provider.

        Args:
            llm_provider: Persisted provider entity.

        Returns:
            Concrete provider client implementation.

        Raises:
            UnsupportedLLMProviderError: If provider type is unsupported.

        """
        if llm_provider.type is LLMProviderType.OLLAMA:
            return OllamaClient(base_url=llm_provider.base_url, timeout=DEFAULT_TIMEOUT)

        raise UnsupportedLLMProviderError
