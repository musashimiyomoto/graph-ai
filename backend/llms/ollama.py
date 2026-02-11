"""Ollama client implementation."""

import httpx

from llms.base import ChatMessage, ChatResponse, LLMClient, LLMModel


class OllamaClient(LLMClient):
    """Client for the Ollama API."""

    def __init__(
        self,
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
        self.__base_url = base_url
        self.__timeout = timeout
        self.__transport = transport

    async def list_models(self) -> list[LLMModel]:
        """List available models from the provider.

        Returns:
            The list of model metadata.

        """
        async with httpx.AsyncClient(
            base_url=self.__base_url,
            timeout=self.__timeout,
            transport=self.__transport,
        ) as client:
            response = await client.get(url="/api/tags")
            response.raise_for_status()
            payload = response.json()

        return [LLMModel(name=model["name"]) for model in payload.get("models", [])]

    async def chat(self, model: str, messages: list[ChatMessage]) -> ChatResponse:
        """Send chat messages to the provider.

        Args:
            model: The model name.
            messages: The chat messages.

        Returns:
            The chat response payload.

        """
        async with httpx.AsyncClient(
            base_url=self.__base_url,
            timeout=self.__timeout,
            transport=self.__transport,
        ) as client:
            response = await client.post(
                url="/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": message.role, "content": message.content}
                        for message in messages
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        message_data = data.get("message") or {}

        return ChatResponse(
            model=str(data.get("model", model)),
            message=ChatMessage(
                role=str(message_data.get("role", "")),
                content=str(message_data.get("content", "")),
            ),
            done=bool(data.get("done", False)),
            raw=data,
        )
