"""Base LLM client protocol."""

from collections.abc import AsyncIterator
from typing import Protocol

from schemas.llm_provider import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    GenerationParams,
    LLMProviderModelResponse,
)


class BaseLLMClient(Protocol):
    """Interface for LLM provider clients."""

    async def list_models(self) -> list[LLMProviderModelResponse]:
        """List available models from provider."""

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        params: GenerationParams | None = None,
    ) -> ChatResponse:
        """Send chat messages to provider."""

    def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        params: GenerationParams | None = None,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Stream chat completion frames from provider.

        Yields a frame per text delta; the final frame carries token usage
        when the provider reports it.
        """
