"""LLM client exports."""

from constants import DEFAULT_TIMEOUT
from enums import LLMProviderType
from exceptions import UnsupportedLLMProviderError
from llms.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMClient,
    LLMModel,
)
from llms.ollama import OllamaClient
from models import LLMProvider


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
        return OllamaClient(base_url=provider.base_url, timeout=DEFAULT_TIMEOUT)

    raise UnsupportedLLMProviderError


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "LLMClient",
    "LLMModel",
    "OllamaClient",
    "get_llm_client",
]
