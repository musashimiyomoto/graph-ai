"""Tests for the background Ollama model-pull worker task."""

from collections.abc import AsyncIterator

import pytest

import worker as worker_module
from exceptions import LLMProviderConnectionError

_PROGRESS = [
    {"status": "pulling manifest"},
    {"status": "downloading", "completed": 50, "total": 100},
    {"status": "success"},
]


class _FakeRedis:
    """Stand-in Redis recording every publish/set call."""

    def __init__(self) -> None:
        """Start with no recorded calls."""
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        """Record a published message."""
        self.published.append((channel, message))

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Accept the snapshot write (only publish order is asserted here)."""
        del key, value, ex


class _StubOllamaClient:
    """Ollama client stub yielding fixed progress objects."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept any constructor args."""
        del args, kwargs

    async def pull_model(self, model: str) -> AsyncIterator[dict[str, object]]:
        """Yield the fixed progress sequence."""
        del model
        for progress in _PROGRESS:
            yield progress


class _FailingOllamaClient:
    """Ollama client stub whose pull fails partway through."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept any constructor args."""
        del args, kwargs

    async def pull_model(self, model: str) -> AsyncIterator[dict[str, object]]:
        """Yield one frame then raise a connection error."""
        del model
        yield {"status": "pulling manifest"}
        raise LLMProviderConnectionError(message="unreachable")


@pytest.mark.asyncio
async def test_publishes_progress_and_terminal_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each progress line is published, followed by a terminal done frame."""
    monkeypatch.setattr(worker_module, "OllamaClient", _StubOllamaClient)
    redis = _FakeRedis()

    await worker_module.pull_ollama_model_task(
        {"redis": redis, "job_id": "job-1"}, "http://ollama:11434", "llama3.2:1b"
    )

    frames = [message for _channel, message in redis.published]
    if len(frames) != len(_PROGRESS) + 1:
        pytest.fail("Expected one frame per progress line plus a terminal frame")
    if '"done": true' not in frames[-1] or "success" not in frames[-1]:
        pytest.fail("Expected a terminal success frame")


@pytest.mark.asyncio
async def test_publishes_error_frame_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed pull publishes an error frame and re-raises for ARQ."""
    monkeypatch.setattr(worker_module, "OllamaClient", _FailingOllamaClient)
    redis = _FakeRedis()

    with pytest.raises(LLMProviderConnectionError):
        await worker_module.pull_ollama_model_task(
            {"redis": redis, "job_id": "job-2"}, "http://ollama:11434", "llama3.2:1b"
        )

    frames = [message for _channel, message in redis.published]
    if not frames or '"error"' not in frames[-1] or '"done": true' not in frames[-1]:
        pytest.fail("Expected a terminal error frame")
