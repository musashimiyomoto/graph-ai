"""Ollama client implementation."""

from __future__ import annotations

import httpx

from llm.base import ChatMessage, ChatResponse, EmbeddingResponse, LLMClient, LLMModel


class OllamaClient(LLMClient):
    """Client for the Ollama API."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the Ollama server.
            timeout: Request timeout in seconds.
            transport: Optional transport for testing.

        """
        self._base_url = base_url
        self._timeout = timeout
        self._transport = transport

    async def list_models(self) -> list[LLMModel]:
        """List available models from the provider.

        Returns:
            The list of model metadata.

        """
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.get(url="/api/tags")
            response.raise_for_status()
            payload = response.json()

        return [LLMModel(name=model["name"]) for model in payload.get("models", [])]

    async def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        options: dict | None,
        stream: bool,
    ) -> ChatResponse:
        """Send chat messages to the provider.

        Args:
            model: The model name.
            messages: The chat messages.
            options: Optional provider options.
            stream: Whether to stream responses.

        Returns:
            The chat response payload.

        """
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }
        if options is not None:
            payload["options"] = options
        if stream:
            payload["stream"] = False

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(url="/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        message_data = data.get("message") or {}
        message = ChatMessage(
            role=str(message_data.get("role", "")),
            content=str(message_data.get("content", "")),
        )
        done = bool(data.get("done", False))
        model_name = str(data.get("model", model))

        return ChatResponse(model=model_name, message=message, done=done, raw=data)

    async def embed(
        self,
        *,
        model: str,
        prompt: str,
        options: dict | None,
    ) -> EmbeddingResponse:
        """Generate embeddings from the provider.

        Args:
            model: The model name.
            prompt: The text prompt.
            options: Optional provider options.

        Returns:
            The embedding response payload.

        """
        payload: dict[str, object] = {"model": model, "prompt": prompt}
        if options is not None:
            payload["options"] = options

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(url="/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()

        embedding = data.get("embedding") or []
        return EmbeddingResponse(embedding=list(embedding), raw=data)
