"""LLM client abstractions and DTOs."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMModel:
    """Model metadata returned by a provider."""

    name: str


@dataclass(frozen=True)
class ChatMessage:
    """Chat message payload."""

    role: str
    content: str


@dataclass(frozen=True)
class ChatResponse:
    """Chat response payload."""

    model: str
    message: ChatMessage
    done: bool
    raw: dict[str, object]


@dataclass(frozen=True)
class ChatRequest:
    """Chat request payload."""

    model: str
    messages: list[ChatMessage]


class LLMClient(Protocol):
    """Interface for LLM client implementations."""

    async def list_models(self) -> list[LLMModel]:
        """List available models from the provider."""

    async def chat(self, model: str, messages: list[ChatMessage]) -> ChatResponse:
        """Send chat messages to the provider."""
