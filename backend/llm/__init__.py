"""AI package exports."""

from constants import DEFAULT_TIMEOUT
from enums import LLMProviderType
from exceptions import LLMProviderConfigError, UnsupportedLLMProviderError
from llm.anthropic import AnthropicClient
from llm.base import BaseLLMClient
from llm.ollama import OllamaClient
from llm.openai import OpenAIClient
from schemas import LLMProviderResponse

_API_KEY_PROVIDERS = {
    LLMProviderType.OPENAI,
    LLMProviderType.ANTHROPIC,
}


def create_llm_client(
    llm_provider: LLMProviderResponse,
    api_key: str | None = None,
) -> BaseLLMClient:
    """Create an LLM client for a configured provider.

    Args:
        llm_provider: Persisted provider entity.
        api_key: Decrypted API key for cloud providers, if configured.

    Returns:
        Concrete provider client implementation.

    Raises:
        LLMProviderConfigError: If a cloud provider is missing its API key.
        UnsupportedLLMProviderError: If provider type is unsupported.

    """
    if llm_provider.type is LLMProviderType.OLLAMA:
        return OllamaClient(base_url=llm_provider.base_url, timeout=DEFAULT_TIMEOUT)

    if llm_provider.type not in _API_KEY_PROVIDERS:
        raise UnsupportedLLMProviderError

    if not api_key:
        raise LLMProviderConfigError(
            message="This provider requires an API key to be configured"
        )

    if llm_provider.type is LLMProviderType.ANTHROPIC:
        return AnthropicClient(
            base_url=llm_provider.base_url,
            api_key=api_key,
            timeout=DEFAULT_TIMEOUT,
        )

    return OpenAIClient(
        base_url=llm_provider.base_url,
        api_key=api_key,
        timeout=DEFAULT_TIMEOUT,
    )


__all__ = ["BaseLLMClient", "create_llm_client"]
