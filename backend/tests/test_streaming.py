"""Token streaming: node token sink and Redis pub/sub round-trip."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from redis.asyncio import Redis

from enums import LLMProviderType
from nodes import NodeValue
from nodes import llm as llm_module
from nodes.base import NodeExecutionContext
from schemas import ChatStreamChunk, TokenUsage
from streaming import (
    publish_pull_progress,
    publish_token,
    pull_channel,
    read_pull_snapshot,
    subscribe_pull_progress,
    subscribe_tokens,
    token_channel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.repositories import ConnectionRepository, LLMProviderRepository

_EXECUTION_ID = 42
_NODE_ID = 7
_DELTAS = ["Hello", ", ", "world"]
_STREAM_PROMPT_TOKENS = 11
_STREAM_COMPLETION_TOKENS = 5


def _execution_id_for_worker(worker_id: str) -> int:
    """Return a pub/sub namespace unique to the active xdist worker."""
    if worker_id == "master":
        return _EXECUTION_ID
    return _EXECUTION_ID + int(worker_id.removeprefix("gw")) + 1


class _StubStreamingClient:
    """LLM client stub that streams a fixed sequence of deltas then usage."""

    def __init__(self, deltas: list[str]) -> None:
        """Store the deltas to emit."""
        self._deltas = deltas

    async def stream_chat(
        self, *args: object, **kwargs: object
    ) -> AsyncIterator[ChatStreamChunk]:
        """Yield the configured deltas, then a final usage frame."""
        del args, kwargs
        for delta in self._deltas:
            yield ChatStreamChunk(delta=delta)
        yield ChatStreamChunk(
            usage=TokenUsage(
                prompt_tokens=_STREAM_PROMPT_TOKENS,
                completion_tokens=_STREAM_COMPLETION_TOKENS,
                total_tokens=_STREAM_PROMPT_TOKENS + _STREAM_COMPLETION_TOKENS,
            )
        )


class _StubProviderRepository:
    """Repository stub returning a fixed Ollama provider row."""

    async def get_by(self, *args: object, **kwargs: object) -> SimpleNamespace:
        """Return a minimal Ollama provider row without an API key."""
        del args, kwargs
        return SimpleNamespace(
            id=1,
            user_id=1,
            name="p",
            type=LLMProviderType.OLLAMA,
            base_url="http://ollama:11434",
            config={},
            connection_id=2,
        )


class _StubConnectionRepository:
    """Repository stub returning one credential-free connection."""

    async def get_by(self, *args: object, **kwargs: object) -> SimpleNamespace:
        """Return a minimal unified connection row."""
        del args, kwargs
        return SimpleNamespace(credentials="encrypted")


class TestNodeTokenSink:
    """Tests for the LLM node streaming path via on_token."""

    @pytest.mark.asyncio
    async def test_streams_and_accumulates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The node forwards each delta and returns the concatenation."""
        monkeypatch.setattr(
            llm_module,
            "create_llm_client",
            lambda **_: _StubStreamingClient(_DELTAS),
        )
        monkeypatch.setattr(llm_module, "connection_secret", lambda _value: None)

        collected: list[str] = []

        async def on_token(delta: str) -> None:
            """Record each streamed delta."""
            collected.append(delta)

        handler = llm_module.LLMNodeHandler(
            llm_provider_repository=cast(
                "LLMProviderRepository", _StubProviderRepository()
            ),
            connection_repository=cast(
                "ConnectionRepository", _StubConnectionRepository()
            ),
        )
        result = await handler.execute(
            NodeExecutionContext(
                session=cast("AsyncSession", None),
                workflow_owner_id=1,
                node_data={"llm_provider_id": 1, "model": "m", "system_prompt": ""},
                parent_values=[NodeValue.text("prompt")],
                input_value=NodeValue.text("prompt"),
                on_token=on_token,
            )
        )

        if collected != _DELTAS:
            pytest.fail("Each delta should have been forwarded to on_token")
        if result.output.require_text() != "".join(_DELTAS):
            pytest.fail("Node output should be the concatenated deltas")
        if result.usage is None:
            pytest.fail("Node result should carry token usage from the stream")
        elif result.usage.total_tokens != (
            _STREAM_PROMPT_TOKENS + _STREAM_COMPLETION_TOKENS
        ):
            pytest.fail("Node usage should match the stream's final usage frame")


class TestTokenPubSub:
    """Tests for the Redis token pub/sub round-trip."""

    def test_channel_name(self) -> None:
        """The channel name is namespaced by execution ID."""
        if token_channel(_EXECUTION_ID) != f"execution:{_EXECUTION_ID}:tokens":
            pytest.fail("Unexpected channel name")

    @pytest.mark.asyncio
    async def test_publish_then_subscribe_round_trip(
        self,
        test_redis: Redis,
        worker_id: str,
    ) -> None:
        """Published deltas are received in order by a subscriber."""
        deltas = ["a", "b", "c"]
        received: list[tuple[int, str]] = []
        ready = asyncio.Event()
        execution_id = _execution_id_for_worker(worker_id)

        async def consume() -> None:
            """Collect published deltas until all arrive."""
            async for node_id, delta, _reset in subscribe_tokens(
                test_redis, execution_id
            ):
                received.append((node_id, delta))
                if len(received) == len(deltas):
                    return

        async def produce() -> None:
            """Publish deltas once the subscription is active."""
            await ready.wait()
            for delta in deltas:
                await publish_token(test_redis, execution_id, _NODE_ID, delta)

        consumer = asyncio.create_task(consume())
        # Give the subscriber a moment to subscribe before publishing.
        await asyncio.sleep(0.2)
        ready.set()
        await produce()
        await asyncio.wait_for(consumer, timeout=5)

        if received != [(_NODE_ID, delta) for delta in deltas]:
            pytest.fail("Subscriber did not receive published deltas in order")


_PULL_JOB_ID = "ollama-pull:1:llama3.2:1b"


class TestOllamaPullPubSub:
    """Tests for the Redis model-pull progress pub/sub round trip."""

    def test_channel_name(self) -> None:
        """The channel name is namespaced by pull job ID."""
        if pull_channel(_PULL_JOB_ID) != f"ollama:pull:{_PULL_JOB_ID}:progress":
            pytest.fail("Unexpected channel name")

    @pytest.mark.asyncio
    async def test_publish_then_subscribe_round_trip(
        self,
        test_redis: Redis,
        worker_id: str,
    ) -> None:
        """Published progress frames are received in order by a subscriber."""
        frames = [
            {"status": "pulling manifest", "done": False},
            {"status": "downloading", "percent": 50, "done": False},
            {"status": "success", "percent": 100, "done": True},
        ]
        received: list[dict] = []
        ready = asyncio.Event()
        pull_job_id = f"{_PULL_JOB_ID}:{worker_id}"

        async def consume() -> None:
            """Collect published frames until all arrive."""
            async for frame in subscribe_pull_progress(test_redis, pull_job_id):
                received.append(frame)
                if len(received) == len(frames):
                    return

        async def produce() -> None:
            """Publish frames once the subscription is active."""
            await ready.wait()
            for frame in frames:
                await publish_pull_progress(test_redis, pull_job_id, frame)

        consumer = asyncio.create_task(consume())
        # Give the subscriber a moment to subscribe before publishing.
        await asyncio.sleep(0.2)
        ready.set()
        await produce()
        await asyncio.wait_for(consumer, timeout=5)

        if received != frames:
            pytest.fail("Subscriber did not receive published frames in order")

    @pytest.mark.asyncio
    async def test_snapshot_holds_last_frame(
        self,
        test_redis: Redis,
        worker_id: str,
    ) -> None:
        """The snapshot key reflects the most recently published frame."""
        pull_job_id = f"{_PULL_JOB_ID}:{worker_id}"
        if await read_pull_snapshot(test_redis, pull_job_id) is not None:
            pytest.fail("Expected no snapshot before any publish")

        await publish_pull_progress(test_redis, pull_job_id, {"status": "start"})
        await publish_pull_progress(
            test_redis, pull_job_id, {"status": "success", "done": True}
        )

        snapshot = await read_pull_snapshot(test_redis, pull_job_id)
        if snapshot != {"status": "success", "done": True}:
            pytest.fail("Snapshot did not reflect the last published frame")
