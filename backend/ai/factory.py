"""LLM client factory."""

from ai.llm import BaseLLMClient, OllamaClient
from constants import DEFAULT_TIMEOUT
from enums import LLMProviderType
from exceptions import UnsupportedLLMProviderError
from schemas import LLMProviderResponse


class LLMClientFactory:
    """Factory for resolving integration client by provider type."""

    def get_client(self, llm_provider: LLMProviderResponse) -> BaseLLMClient:
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
