"""AI package exports."""

from ai.llm import BaseLLMClient, OllamaClient
from constants import DEFAULT_TIMEOUT
from enums import LLMProviderType
from exceptions import UnsupportedLLMProviderError
from schemas import LLMProviderResponse


def create_llm_client(llm_provider: LLMProviderResponse) -> BaseLLMClient:
    """Create an LLM client for a configured provider.

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


__all__ = ["BaseLLMClient", "create_llm_client"]
