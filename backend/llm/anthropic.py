"""Anthropic LLM client."""

import contextlib
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Literal

import anthropic
from anthropic.types import MessageParam, TextBlock, TextBlockParam

from constants import DEFAULT_ANTHROPIC_MAX_TOKENS
from exceptions import LLMProviderConfigError, LLMProviderConnectionError
from schemas.llm_provider import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    GenerationParams,
    LLMProviderModelResponse,
    TokenUsage,
)


@contextlib.contextmanager
def _wrap_anthropic_errors() -> Iterator[None]:
    """Translate Anthropic SDK errors into domain exceptions.

    Yields:
        Control to the wrapped request block.

    Raises:
        LLMProviderConfigError: If the provider rejects the request as invalid.
        LLMProviderConnectionError: If the provider is unreachable or transient.

    """
    try:
        yield
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise LLMProviderConfigError(
            message="Anthropic provider rejected the API key"
        ) from exc
    except anthropic.BadRequestError as exc:
        raise LLMProviderConfigError(
            message=f"Anthropic provider rejected the request: {exc.message[:300]}"
        ) from exc
    except anthropic.APIStatusError as exc:
        raise LLMProviderConnectionError(
            message=f"Anthropic provider returned {exc.status_code}"
        ) from exc
    except anthropic.APIError as exc:
        raise LLMProviderConnectionError(
            message="Anthropic provider is unreachable"
        ) from exc


@dataclass(frozen=True)
class _AnthropicRequest:
    """Resolved Anthropic request arguments."""

    max_tokens: int
    system: list[TextBlockParam] | anthropic.Omit
    turns: list[MessageParam]
    temperature: float | anthropic.Omit
    top_p: float | anthropic.Omit


def _resolve_request(
    messages: list[ChatMessage],
    params: GenerationParams | None,
) -> _AnthropicRequest:
    """Build the resolved Anthropic request arguments.

    Args:
        messages: Ordered chat messages.
        params: Optional generation parameters.

    Returns:
        Resolved request arguments with omit sentinels for unset fields.

    """
    system_prompt, turns = _split_system(messages)
    max_tokens = DEFAULT_ANTHROPIC_MAX_TOKENS
    temperature: float | anthropic.Omit = anthropic.omit
    top_p: float | anthropic.Omit = anthropic.omit
    if params is not None:
        if params.max_tokens is not None:
            max_tokens = params.max_tokens
        if params.temperature is not None:
            temperature = params.temperature
        if params.top_p is not None:
            top_p = params.top_p

    system: list[TextBlockParam] | anthropic.Omit = (
        [TextBlockParam(type="text", text=system_prompt)]
        if system_prompt
        else anthropic.omit
    )
    return _AnthropicRequest(
        max_tokens=max_tokens,
        system=system,
        turns=turns,
        temperature=temperature,
        top_p=top_p,
    )


def _split_system(
    messages: list[ChatMessage],
) -> tuple[str, list[MessageParam]]:
    """Separate system messages from the conversation turns.

    Args:
        messages: Ordered chat messages.

    Returns:
        A tuple of the joined system prompt and the remaining turns as
        Anthropic message params.

    """
    system_parts: list[str] = []
    turns: list[MessageParam] = []
    for message in messages:
        if message.role == "system":
            if message.content:
                system_parts.append(message.content)
            continue
        role: Literal["user", "assistant"] = (
            "assistant" if message.role == "assistant" else "user"
        )
        turns.append({"role": role, "content": message.content})

    return "\n".join(system_parts), turns


def _usage_from_message(usage: object) -> TokenUsage | None:
    """Normalize an Anthropic ``usage`` object into a `TokenUsage`.

    Anthropic reports ``input_tokens``/``output_tokens`` and no explicit
    total, so the total is derived as their sum.

    Args:
        usage: The SDK's ``Usage`` object (or ``None`` if absent).

    Returns:
        Normalized token usage, or ``None`` when the provider omitted it.

    """
    if usage is None:
        return None
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


class AnthropicClient:
    """Client for the Anthropic Messages API."""

    def __init__(
        self,
        base_url: str | None,
        api_key: str,
        timeout: float,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL override; None uses the Anthropic default endpoint.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.

        """
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    async def list_models(self) -> list[LLMProviderModelResponse]:
        """List available models from provider.

        Returns:
            Model metadata list.

        Raises:
            LLMProviderConfigError: If the provider rejects the request.
            LLMProviderConnectionError: If the provider is unreachable.

        """
        with _wrap_anthropic_errors():
            return [
                LLMProviderModelResponse(name=model.id)
                async for model in self._client.models.list()
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
            LLMProviderConfigError: If the provider rejects the request.
            LLMProviderConnectionError: If the provider is unreachable.

        """
        request = _resolve_request(messages, params)

        with _wrap_anthropic_errors():
            async with self._client.messages.stream(
                model=model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=request.turns,
                temperature=request.temperature,
                top_p=request.top_p,
            ) as stream:
                message = await stream.get_final_message()

        content = "".join(
            block.text for block in message.content if isinstance(block, TextBlock)
        )
        return ChatResponse(
            model=message.model,
            message=ChatMessage(role=message.role, content=content),
            done=message.stop_reason != "max_tokens",
            raw=message.model_dump(),
            usage=_usage_from_message(message.usage),
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
            LLMProviderConfigError: If the provider rejects the request.
            LLMProviderConnectionError: If the provider is unreachable.

        """
        request = _resolve_request(messages, params)

        with _wrap_anthropic_errors():
            async with self._client.messages.stream(
                model=model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=request.turns,
                temperature=request.temperature,
                top_p=request.top_p,
            ) as stream:
                async for text in stream.text_stream:
                    yield ChatStreamChunk(delta=text)
                # The accumulated final message carries the authoritative
                # input/output token counts for the whole stream.
                final_message = await stream.get_final_message()
            usage = _usage_from_message(final_message.usage)
            if usage is not None:
                yield ChatStreamChunk(usage=usage)
