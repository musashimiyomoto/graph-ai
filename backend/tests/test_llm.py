"""LLM client, factory, and generation-parameter tests."""

import json
from collections.abc import AsyncIterator
from typing import Self, cast

import pytest

from enums import LLMProviderType
from exceptions import ExecutionGraphValidationError, LLMProviderConfigError
from llm import create_llm_client
from llm.anthropic import AnthropicClient, _split_system
from llm.ollama import OllamaClient, _build_options
from llm.openai import OpenAIClient, _to_openai_messages
from nodes.llm import _build_generation_params
from schemas import ChatMessage, GenerationParams, LLMProviderResponse

_EXPECTED_TEMPERATURE = 0.5
_EXPECTED_MAX_TOKENS = 128


def _make_provider(provider_type: LLMProviderType) -> LLMProviderResponse:
    """Build a provider response for factory tests."""
    return LLMProviderResponse(
        id=1,
        user_id=1,
        name="provider",
        type=provider_type,
        base_url="https://example.com",
        config={},
    )


class TestGenerationParams:
    """Tests for building generation params from node data."""

    def test_none_when_absent(self) -> None:
        """No configured params yields None."""
        if _build_generation_params({"model": "m"}) is not None:
            pytest.fail("Expected no generation params")

    def test_ignores_null_values(self) -> None:
        """Explicit null values are treated as unset."""
        if _build_generation_params({"temperature": None, "top_p": None}) is not None:
            pytest.fail("Null values must be treated as unset")

    def test_builds_subset(self) -> None:
        """Only configured params are included."""
        params = _build_generation_params(
            {"temperature": _EXPECTED_TEMPERATURE, "max_tokens": _EXPECTED_MAX_TOKENS}
        )
        if params is None:
            pytest.fail("Expected generation params")
        elif (
            params.temperature != _EXPECTED_TEMPERATURE
            or params.max_tokens != _EXPECTED_MAX_TOKENS
        ):
            pytest.fail("Params did not match node data")
        elif params.top_p is not None:
            pytest.fail("Unset param must remain None")

    def test_invalid_value_raises(self) -> None:
        """An out-of-range value raises a graph validation error."""
        with pytest.raises(ExecutionGraphValidationError):
            _build_generation_params({"temperature": 5})


class TestOllamaOptions:
    """Tests for Ollama option translation."""

    def test_empty_without_params(self) -> None:
        """No params yields no options."""
        if _build_options(None) != {}:
            pytest.fail("Expected empty options")

    def test_maps_fields(self) -> None:
        """Generation params map onto Ollama option names."""
        options = _build_options(
            GenerationParams(temperature=0.2, max_tokens=64, top_p=0.9)
        )
        if options != {"temperature": 0.2, "num_predict": 64, "top_p": 0.9}:
            pytest.fail("Options did not map correctly")


class TestOllamaChat:
    """Tests for the Ollama chat request payload."""

    @pytest.mark.asyncio
    async def test_sends_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Generation params are forwarded as Ollama options."""
        captured: dict[str, object] = {}

        class DummyResponse:
            """Fixed Ollama chat response."""

            status_code = 200
            text = ""

            def raise_for_status(self) -> None:
                """Keep the successful status."""

            def json(self) -> dict:
                """Return a mock chat payload."""
                return {
                    "model": "m",
                    "message": {"role": "assistant", "content": "ok"},
                    "done": True,
                }

        class DummyAsyncClient:
            """Async client capturing the posted body."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Accept any httpx kwargs."""

            async def __aenter__(self) -> Self:
                """Enter the context manager."""
                return self

            async def __aexit__(self, *args: object) -> bool:
                """Exit the context manager."""
                return False

            async def post(self, *args: object, **kwargs: object) -> DummyResponse:
                """Record the request body and return a response."""
                del args
                captured.update(kwargs)
                return DummyResponse()

        monkeypatch.setattr("llm.ollama.httpx.AsyncClient", DummyAsyncClient)

        client = OllamaClient(base_url="http://ollama:11434", timeout=1.0)
        await client.chat(
            model="m",
            messages=[ChatMessage(role="user", content="hi")],
            params=GenerationParams(temperature=0.3),
        )

        body = cast("dict[str, object]", captured.get("json"))
        if body.get("options") != {"temperature": 0.3}:
            pytest.fail("Options were not forwarded to Ollama")


_STREAM_LINES = [
    '{"message": {"content": "Hel"}}',
    '{"message": {"content": "lo"}}',
    "",
    '{"message": {"content": ""}, "done": true}',
]


class _DummyStreamResponse:
    """Streamed Ollama response yielding NDJSON lines."""

    status_code = 200

    async def aread(self) -> bytes:
        """Return an empty body (unused on success)."""
        return b""

    def raise_for_status(self) -> None:
        """Keep the successful status."""

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Yield the fixed NDJSON lines."""
        for line in _STREAM_LINES:
            yield line


class _DummyStreamCtx:
    """Async context manager returning the streamed response."""

    async def __aenter__(self) -> _DummyStreamResponse:
        """Enter and return the response."""
        return _DummyStreamResponse()

    async def __aexit__(self, *args: object) -> bool:
        """Exit the context manager."""
        return False


class _DummyStreamingClient:
    """Async client whose stream() returns fixed NDJSON lines."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept any httpx kwargs."""

    async def __aenter__(self) -> Self:
        """Enter the client context manager."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit the client context manager."""
        return False

    def stream(self, *args: object, **kwargs: object) -> _DummyStreamCtx:
        """Return the streaming response context manager."""
        del args, kwargs
        return _DummyStreamCtx()


class TestOllamaStreamChat:
    """Tests for streaming Ollama chat deltas."""

    @pytest.mark.asyncio
    async def test_yields_deltas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NDJSON stream lines are parsed into content deltas."""
        monkeypatch.setattr("llm.ollama.httpx.AsyncClient", _DummyStreamingClient)

        client = OllamaClient(base_url="http://ollama:11434", timeout=1.0)
        collected = [
            delta
            async for delta in client.stream_chat(
                model="m", messages=[ChatMessage(role="user", content="hi")]
            )
        ]

        if collected != ["Hel", "lo"]:
            pytest.fail("Stream did not yield the expected content deltas")


_PULL_LINES = [
    '{"status": "pulling manifest"}',
    '{"status": "downloading", "completed": 50, "total": 100}',
    '{"status": "success"}',
]


class _DummyPullStreamResponse:
    """Streamed Ollama pull response yielding fixed NDJSON progress lines."""

    status_code = 200

    async def aread(self) -> bytes:
        """Return an empty body (unused on success)."""
        return b""

    def raise_for_status(self) -> None:
        """Keep the successful status."""

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Yield the fixed NDJSON progress lines."""
        for line in _PULL_LINES:
            yield line


class _DummyPullStreamCtx:
    """Async context manager returning the streamed pull response."""

    async def __aenter__(self) -> _DummyPullStreamResponse:
        """Enter and return the response."""
        return _DummyPullStreamResponse()

    async def __aexit__(self, *args: object) -> bool:
        """Exit the context manager."""
        return False


class _DummyPullStreamingClient:
    """Async client whose stream() returns fixed pull progress lines."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept any httpx kwargs."""

    async def __aenter__(self) -> Self:
        """Enter the client context manager."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit the client context manager."""
        return False

    def stream(self, *args: object, **kwargs: object) -> _DummyPullStreamCtx:
        """Return the streaming response context manager."""
        del args, kwargs
        return _DummyPullStreamCtx()


class TestOllamaPullModel:
    """Tests for streaming an Ollama model pull."""

    @pytest.mark.asyncio
    async def test_yields_progress_objects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each NDJSON line is parsed and yielded as a progress object."""
        monkeypatch.setattr("llm.ollama.httpx.AsyncClient", _DummyPullStreamingClient)

        client = OllamaClient(base_url="http://ollama:11434", timeout=1.0)
        collected = [progress async for progress in client.pull_model("llama3.2:1b")]

        if collected != [json.loads(line) for line in _PULL_LINES]:
            pytest.fail("Pull progress lines were not parsed correctly")


class TestOllamaDeleteModel:
    """Tests for deleting an Ollama model."""

    @pytest.mark.asyncio
    async def test_sends_delete_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The model name is sent as a DELETE /api/delete request body."""
        captured: dict[str, object] = {}

        class DummyResponse:
            """Fixed successful delete response."""

            status_code = 200
            text = ""

            def raise_for_status(self) -> None:
                """Keep the successful status."""

        class DummyAsyncClient:
            """Async client capturing the delete request."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Accept any httpx kwargs."""

            async def __aenter__(self) -> Self:
                """Enter the context manager."""
                return self

            async def __aexit__(self, *args: object) -> bool:
                """Exit the context manager."""
                return False

            async def request(
                self, method: str, *_args: object, **kwargs: object
            ) -> DummyResponse:
                """Record the request method/body and return a response."""
                captured["method"] = method
                captured.update(kwargs)
                return DummyResponse()

        monkeypatch.setattr("llm.ollama.httpx.AsyncClient", DummyAsyncClient)

        client = OllamaClient(base_url="http://ollama:11434", timeout=1.0)
        await client.delete_model("llama3.2:1b")

        if captured.get("method") != "DELETE":
            pytest.fail("Expected a DELETE request")
        if captured.get("json") != {"model": "llama3.2:1b"}:
            pytest.fail("Expected the model name in the delete request body")


class TestAnthropicSplitSystem:
    """Tests for separating system messages for Anthropic."""

    def test_extracts_system_and_maps_roles(self) -> None:
        """System messages are joined; remaining turns keep valid roles."""
        system, turns = _split_system(
            [
                ChatMessage(role="system", content="be nice"),
                ChatMessage(role="user", content="hello"),
                ChatMessage(role="assistant", content="hi"),
            ]
        )
        if system != "be nice":
            pytest.fail("System prompt was not extracted")
        if [turn["role"] for turn in turns] != ["user", "assistant"]:
            pytest.fail("Turn roles were not preserved")


class TestOpenAIMessages:
    """Tests for OpenAI message translation."""

    def test_maps_roles(self) -> None:
        """Each role maps to the matching OpenAI param role."""
        params = _to_openai_messages(
            [
                ChatMessage(role="system", content="s"),
                ChatMessage(role="user", content="u"),
                ChatMessage(role="assistant", content="a"),
            ]
        )
        if [param["role"] for param in params] != ["system", "user", "assistant"]:
            pytest.fail("Roles were not mapped correctly")


class TestCreateLLMClient:
    """Tests for the LLM client factory."""

    def test_ollama_needs_no_key(self) -> None:
        """The Ollama provider builds without an API key."""
        client = create_llm_client(_make_provider(LLMProviderType.OLLAMA))
        if not isinstance(client, OllamaClient):
            pytest.fail("Expected an Ollama client")

    def test_cloud_requires_key(self) -> None:
        """Cloud providers without an API key are rejected."""
        with pytest.raises(LLMProviderConfigError):
            create_llm_client(_make_provider(LLMProviderType.OPENAI))

    def test_openai_with_key(self) -> None:
        """The OpenAI provider builds an OpenAI client with a key."""
        client = create_llm_client(
            _make_provider(LLMProviderType.OPENAI), api_key="sk-test"
        )
        if not isinstance(client, OpenAIClient):
            pytest.fail("Expected an OpenAI client")

    def test_anthropic_with_key(self) -> None:
        """The Anthropic provider builds an Anthropic client with a key."""
        client = create_llm_client(
            _make_provider(LLMProviderType.ANTHROPIC), api_key="sk-test"
        )
        if not isinstance(client, AnthropicClient):
            pytest.fail("Expected an Anthropic client")
