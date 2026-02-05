"""LLM provider enums."""

from enum import StrEnum, auto


class LLMProviderType(StrEnum):
    """Supported large language model providers."""

    OLLAMA = auto()
