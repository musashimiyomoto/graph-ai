"""LLM client factory."""

from enums import LLMProviderType
from exceptions import UnsupportedLLMProviderError
from llm.base import LLMClient
from llm.ollama import OllamaClient
from models import LLMProvider
from settings import llm_settings


def get_llm_client(provider: LLMProvider) -> LLMClient:
    """Create an LLM client for a provider.

    Args:
        provider: The LLM provider model.

    Returns:
        A concrete LLM client.

    Raises:
        UnsupportedLLMProviderError: If the provider type is not supported.

    """
    if provider.type is LLMProviderType.OLLAMA:
        base_url = provider.base_url or llm_settings.default_base_url
        return OllamaClient(
            base_url=base_url,
            timeout=llm_settings.request_timeout,
        )

    raise UnsupportedLLMProviderError
