"""LLM client tests."""

import json

import httpx
import pytest

from llm import ChatMessage, OllamaClient


class TestOllamaClient:
    """Tests for the Ollama client."""

    @pytest.mark.asyncio
    async def test_list_models(self) -> None:
        """List models parses tag payloads without auth headers."""
        seen_auth: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_auth.append(request.headers.get("Authorization"))
            if request.url.path != "/api/tags":
                pytest.fail(f"Unexpected path: {request.url.path}")
            return httpx.Response(200, json={"models": [{"name": "llama3"}]})

        client = OllamaClient(
            base_url="http://ollama",
            timeout=5.0,
            transport=httpx.MockTransport(handler),
        )

        models = await client.list_models()

        if len(models) != 1 or models[0].name != "llama3":
            pytest.fail("Expected a single model named 'llama3'")
        if any(value is not None for value in seen_auth):
            pytest.fail("Authorization header must not be set")

    @pytest.mark.asyncio
    async def test_chat(self) -> None:
        """Chat requests serialize messages and disable streaming."""
        seen_auth: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_auth.append(request.headers.get("Authorization"))
            payload = json.loads(request.content)
            if payload.get("stream") is not False:
                pytest.fail("Expected stream to be False")
            if payload.get("messages") != [{"role": "user", "content": "hello"}]:
                pytest.fail("Unexpected chat payload")
            return httpx.Response(
                200,
                json={
                    "model": payload.get("model"),
                    "message": {"role": "assistant", "content": "hi"},
                    "done": True,
                },
            )

        client = OllamaClient(
            base_url="http://ollama",
            timeout=5.0,
            transport=httpx.MockTransport(handler),
        )

        response = await client.chat(
            model="llama3",
            messages=[ChatMessage(role="user", content="hello")],
            options=None,
            stream=True,
        )

        if response.model != "llama3" or response.done is not True:
            pytest.fail("Unexpected chat response data")
        if response.message.content != "hi":
            pytest.fail("Unexpected chat response message")
        if any(value is not None for value in seen_auth):
            pytest.fail("Authorization header must not be set")

    @pytest.mark.asyncio
    async def test_embeddings(self) -> None:
        """Embedding requests parse responses without auth headers."""
        seen_auth: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_auth.append(request.headers.get("Authorization"))
            payload = json.loads(request.content)
            if payload.get("prompt") != "embed me":
                pytest.fail("Unexpected embeddings payload")
            return httpx.Response(200, json={"embedding": [0.1, 0.2]})

        client = OllamaClient(
            base_url="http://ollama",
            timeout=5.0,
            transport=httpx.MockTransport(handler),
        )

        response = await client.embed(
            model="llama3",
            prompt="embed me",
            options=None,
        )

        if response.embedding != [0.1, 0.2]:
            pytest.fail("Unexpected embedding vector")
        if any(value is not None for value in seen_auth):
            pytest.fail("Authorization header must not be set")
