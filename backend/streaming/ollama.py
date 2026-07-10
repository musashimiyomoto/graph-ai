"""Redis pub/sub for streaming Ollama model-pull progress to clients.

Mirrors ``streaming.tokens``: the worker publishes progress frames while an
``ollama pull`` runs, and the SSE endpoint forwards them. A last-frame snapshot
key is also kept so a client that connects after the pull already finished still
receives a terminal frame instead of hanging on a channel with no more traffic.
"""

import json
from collections.abc import AsyncIterator

from redis.asyncio import Redis

# Snapshot outlives the pull by an hour so a late-connecting client can still
# read the terminal frame.
_SNAPSHOT_TTL_SECONDS = 3600


def pull_channel(job_id: str) -> str:
    """Return the pub/sub channel name for a pull job's progress stream."""
    return f"ollama:pull:{job_id}:progress"


def _snapshot_key(job_id: str) -> str:
    """Return the key holding a pull job's most recent progress frame."""
    return f"ollama:pull:{job_id}:snapshot"


async def publish_pull_progress(
    redis: Redis, job_id: str, frame: dict[str, object]
) -> None:
    """Publish one progress frame and update the job's snapshot.

    Args:
        redis: Redis connection.
        job_id: The pull job ID.
        frame: The progress payload (``status``/``percent``/``done``/``error``).

    """
    message = json.dumps(frame)
    await redis.publish(pull_channel(job_id), message)
    await redis.set(_snapshot_key(job_id), message, ex=_SNAPSHOT_TTL_SECONDS)


async def read_pull_snapshot(redis: Redis, job_id: str) -> dict[str, object] | None:
    """Return the job's last published frame, or None if there is none yet."""
    raw = await redis.get(_snapshot_key(job_id))
    if raw is None:
        return None
    return json.loads(raw.decode() if isinstance(raw, bytes) else raw)


async def subscribe_pull_progress(
    redis: Redis, job_id: str
) -> AsyncIterator[dict[str, object]]:
    """Yield each progress frame published for a pull job.

    Args:
        redis: Redis connection.
        job_id: The pull job ID.

    Yields:
        Progress frames until the subscription is cancelled by the caller.

    """
    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(pull_channel(job_id))
    try:
        async for message in pubsub.listen():
            raw = message["data"]
            data = raw.decode() if isinstance(raw, bytes) else raw
            yield json.loads(data)
    finally:
        await pubsub.unsubscribe(pull_channel(job_id))
        await pubsub.aclose()
