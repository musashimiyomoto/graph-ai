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
    options: dict | None
    stream: bool


@dataclass(frozen=True)
class EmbeddingResponse:
    """Embedding response payload."""

    embedding: list[float]
    raw: dict[str, object]


@dataclass(frozen=True)
class EmbeddingRequest:
    """Embedding request payload."""

    model: str
    prompt: str
    options: dict | None


class LLMClient(Protocol):
    """Interface for LLM client implementations."""

    async def list_models(self) -> list[LLMModel]:
        """List available models from the provider."""

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        options: dict | None,
        stream: bool,
    ) -> ChatResponse:
        """Send chat messages to the provider."""

    async def embed(
        self,
        *,
        model: str,
        prompt: str,
        options: dict | None,
    ) -> EmbeddingResponse:
        """Generate embeddings from the provider."""
