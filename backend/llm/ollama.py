"""Ollama LLM client."""

import contextlib
import json
from collections.abc import AsyncIterator, Iterator
from http import HTTPStatus

import httpx

from exceptions import LLMProviderConnectionError
from llm.base import BaseLLMClient
from schemas.llm_provider import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    GenerationParams,
    LLMProviderModelResponse,
    TokenUsage,
)


@contextlib.contextmanager
def _wrap_httpx_errors() -> Iterator[None]:
    """Translate httpx transport errors into a domain connection error.

    Yields:
        Control to the wrapped request block.

    Raises:
        LLMProviderConnectionError: If an httpx error is raised.

    """
    try:
        yield
    except httpx.TimeoutException as exc:
        raise LLMProviderConnectionError(message="Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        message = f"Ollama returned {exc.response.status_code}"
        if detail:
            message = f"{message}: {detail[:300]}"
        raise LLMProviderConnectionError(message=message) from exc
    except httpx.HTTPError as exc:
        raise LLMProviderConnectionError from exc


def _usage_from_payload(payload: dict[str, object]) -> TokenUsage | None:
    """Normalize an Ollama response payload's token counts into a `TokenUsage`.

    Ollama reports ``prompt_eval_count``/``eval_count`` on its final (``done``)
    response object and no explicit total, so the total is their sum. Returns
    ``None`` when neither count is present.

    Args:
        payload: A parsed Ollama ``/api/chat`` response object.

    Returns:
        Normalized token usage, or ``None`` when no counts are present.

    """
    prompt = payload.get("prompt_eval_count")
    completion = payload.get("eval_count")
    if not isinstance(prompt, int) and not isinstance(completion, int):
        return None
    prompt_tokens = prompt if isinstance(prompt, int) else 0
    completion_tokens = completion if isinstance(completion, int) else 0
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _build_options(params: GenerationParams | None) -> dict[str, float | int]:
    """Translate generation params into Ollama option fields.

    Args:
        params: Optional generation parameters.

    Returns:
        Ollama options payload, empty when no params are set.

    """
    if params is None:
        return {}

    options: dict[str, float | int] = {}
    if params.temperature is not None:
        options["temperature"] = params.temperature
    if params.max_tokens is not None:
        options["num_predict"] = params.max_tokens
    if params.top_p is not None:
        options["top_p"] = params.top_p
    return options


class OllamaClient(BaseLLMClient):
    """Client for the Ollama API."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the Ollama server.
            timeout: Request timeout in seconds.

        """
        self._base_url = base_url
        self._timeout = timeout

    async def list_models(self) -> list[LLMProviderModelResponse]:
        """List available models from provider.

        Returns:
            Model metadata list.

        Raises:
            LLMProviderConnectionError: If the provider is unreachable.

        """
        with _wrap_httpx_errors():
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.get(url="/api/tags")
                response.raise_for_status()
                payload = response.json()

        return [
            LLMProviderModelResponse(name=model["name"])
            for model in payload.get("models", [])
        ]

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        params: GenerationParams | None = None,
    ) -> ChatResponse:
        """Send chat messages to provider.

        Args:
            model: Model name.
            messages: Chat messages.
            params: Optional generation parameters.

        Returns:
            Chat response payload.

        Raises:
            LLMProviderConnectionError: If the provider is unreachable.

        """
        request_body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }
        options = _build_options(params)
        if options:
            request_body["options"] = options

        with _wrap_httpx_errors():
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.post(url="/api/chat", json=request_body)
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
            usage=_usage_from_payload(data),
        )

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        params: GenerationParams | None = None,
    ) -> AsyncIterator[ChatStreamChunk]:
        """Stream chat completion frames from provider.

        Args:
            model: Model name.
            messages: Chat messages.
            params: Optional generation parameters.

        Yields:
            A frame per text delta; a final frame carrying token usage.

        Raises:
            LLMProviderConnectionError: If the provider is unreachable.

        """
        request_body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": True,
        }
        options = _build_options(params)
        if options:
            request_body["options"] = options

        with _wrap_httpx_errors():
            async with (
                httpx.AsyncClient(
                    base_url=self._base_url, timeout=self._timeout
                ) as client,
                client.stream("POST", "/api/chat", json=request_body) as response,
            ):
                if response.status_code >= HTTPStatus.BAD_REQUEST:
                    await response.aread()
                    response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    delta = (payload.get("message") or {}).get("content")
                    if delta:
                        yield ChatStreamChunk(delta=delta)
                    # The terminal NDJSON line (done=True) carries the token
                    # counts for the whole generation.
                    if payload.get("done"):
                        usage = _usage_from_payload(payload)
                        if usage is not None:
                            yield ChatStreamChunk(usage=usage)

    async def pull_model(self, model: str) -> AsyncIterator[dict[str, object]]:
        """Pull a model into the server, streaming download progress.

        Args:
            model: Model name/tag to pull (e.g. ``llama3.2:1b``).

        Yields:
            Each raw progress object from Ollama's ``/api/pull`` NDJSON stream:
            a ``status`` string and, for download layers, ``completed``/``total``
            byte counts.

        Raises:
            LLMProviderConnectionError: If the provider is unreachable.

        """
        # A model download can take minutes; disable the read timeout so a slow
        # layer doesn't abort the pull mid-stream (connect timeout is kept).
        timeout = httpx.Timeout(self._timeout, read=None)
        with _wrap_httpx_errors():
            async with (
                httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client,
                client.stream("POST", "/api/pull", json={"model": model}) as response,
            ):
                if response.status_code >= HTTPStatus.BAD_REQUEST:
                    await response.aread()
                    response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    yield json.loads(line)

    async def delete_model(self, model: str) -> None:
        """Delete a model from the server.

        Args:
            model: Model name/tag to delete.

        Raises:
            LLMProviderConnectionError: If the provider is unreachable.

        """
        with _wrap_httpx_errors():
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout
            ) as client:
                response = await client.request(
                    "DELETE", "/api/delete", json={"model": model}
                )
                response.raise_for_status()
