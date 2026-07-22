"""ARQ worker for background workflow execution."""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from arq import cron
from arq.typing import WorkerCoroutine

from api.metrics import record_execution
from artifacts import artifact_store
from channels import (
    ChannelDefinition,
    deliver_execution,
    polling_channel_definitions,
    receive_channel,
)
from constants import DEFAULT_TIMEOUT
from enums import ExecutionSource, ExecutionStatus
from exceptions import BaseError
from llm.ollama import OllamaClient
from logging_config import configure_logging
from observability import init_sentry
from rag.qdrant import get_qdrant_client
from sessions import async_session
from settings import artifact_settings, redis_settings
from streaming import publish_pull_progress, publish_token, publish_token_reset
from usecases import ArtifactUsecase, ExecutionUsecase, VectorUsecase

if TYPE_CHECKING:
    from arq import ArqRedis
    from redis.asyncio import Redis

    from schemas import ExecutionResponse

logger = logging.getLogger(__name__)

# Reap stuck executions every 5 minutes.
_REAPER_MINUTES = set(range(0, 60, 5))
# Artifact retention cleanup runs once an hour in bounded batches.
_ARTIFACT_GC_MINUTES = {17}


async def run_execution_task(ctx: dict[Any, Any], execution_id: int) -> None:
    """Run a workflow execution by ID on the worker.

    Args:
        ctx: ARQ job context.
        execution_id: The execution to run.

    """
    logger.info("Running execution %s", execution_id)
    redis: ArqRedis = ctx["redis"]

    async def token_publisher(exec_id: int, node_id: int, delta: str) -> None:
        """Publish a node token delta to the execution's stream channel."""
        await publish_token(redis, exec_id, node_id, delta)

    async def token_reset_publisher(exec_id: int, node_id: int) -> None:
        """Signal a node retry so clients discard its already-streamed text."""
        await publish_token_reset(redis, exec_id, node_id)

    async with async_session() as session:
        result = await ExecutionUsecase().run_execution(
            session=session,
            execution_id=execution_id,
            session_factory=async_session,
            token_publisher=token_publisher,
            token_reset_publisher=token_reset_publisher,
        )
        if result.status is ExecutionStatus.WAITING_APPROVAL:
            return
        if result.status is ExecutionStatus.WAITING_DELAY:
            if result.wait_until is None or result.queue_job_id is None:
                logger.error(
                    "Execution %s has an incomplete Delay checkpoint", execution_id
                )
                return
            await redis.enqueue_job(
                "run_execution_task",
                execution_id,
                _job_id=result.queue_job_id,
                _defer_until=result.wait_until,
            )
            return
        await deliver_execution(session=session, execution_id=execution_id)

    _record_execution_metrics(result)


def _record_execution_metrics(result: "ExecutionResponse") -> None:
    """Emit Prometheus counters/histograms for a finalized execution.

    Best-effort observability only — a metrics failure must never fail the run.

    Args:
        result: The finalized execution.

    """
    duration = 0.0
    if result.finished_at is not None:
        duration = max(0.0, (result.finished_at - result.started_at).total_seconds())
    record_execution(
        status=result.status.value,
        duration_seconds=duration,
        total_tokens=result.total_tokens or 0,
    )


async def ingest_document_task(
    ctx: dict[Any, Any],
    collection: str,
    filename: str,
    content: bytes,
    source: str | None,
) -> dict[str, Any]:
    """Extract, chunk, embed, and store an uploaded document in the background.

    Enqueued by the Vector Collections upload endpoint so the HTTP request can
    return immediately. Reuses ``VectorUsecase.upload_document`` for all
    validation (size, type, empty); any domain error it raises is recorded by
    ARQ as a failed job and surfaced back through the job-status endpoint.

    Args:
        ctx: ARQ job context.
        collection: Collection to store chunks in. Created if missing.
        filename: The uploaded file's original name.
        content: The file's raw bytes.
        source: Document identifier to use instead of the filename, if given.

    Returns:
        The ingest result (``source`` and ``chunks_ingested``) as a dict, which
        ARQ stores as the job result.

    """
    del ctx
    logger.info("Ingesting %r into collection %r", filename, collection)
    client = get_qdrant_client()
    try:
        result = await VectorUsecase(client).upload_document(
            collection=collection,
            filename=filename,
            content=content,
            source_override=source,
        )
    finally:
        await client.close()
    return result.model_dump()


def _pull_frame(progress: dict[str, object]) -> dict[str, object]:
    """Translate one Ollama pull progress object into a client-facing frame."""
    frame: dict[str, object] = {
        "status": str(progress.get("status", "")),
        "done": False,
    }
    total = progress.get("total")
    completed = progress.get("completed")
    if isinstance(total, int | float) and total and isinstance(completed, int | float):
        frame["percent"] = round(completed / total * 100)
    return frame


async def pull_ollama_model_task(
    ctx: dict[Any, Any], base_url: str, model: str
) -> None:
    """Pull an Ollama model in the background, streaming progress over Redis.

    Publishes a progress frame per line of Ollama's ``/api/pull`` stream and a
    terminal ``done``/``error`` frame, which the SSE endpoint forwards to the
    client. Keyed by this job's own id (``ctx["job_id"]``).

    Args:
        ctx: ARQ job context.
        base_url: The Ollama server base URL.
        model: The model name/tag to pull.

    """
    redis: Redis = ctx["redis"]
    job_id = ctx["job_id"]
    logger.info("Pulling Ollama model %r from %s", model, base_url)
    client = OllamaClient(base_url=base_url, timeout=DEFAULT_TIMEOUT)
    try:
        async for progress in client.pull_model(model):
            await publish_pull_progress(redis, job_id, _pull_frame(progress))
    except BaseError as exc:
        await publish_pull_progress(
            redis, job_id, {"status": "error", "error": exc.message, "done": True}
        )
        raise
    await publish_pull_progress(
        redis, job_id, {"status": "success", "percent": 100, "done": True}
    )


async def poll_registered_channel(
    ctx: dict[Any, Any],
    source: ExecutionSource,
    *args: object,
    **kwargs: object,
) -> None:
    """Run one polling channel through the generic receive/acknowledge runtime."""
    del args, kwargs
    redis: ArqRedis = ctx["redis"]

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await redis.enqueue_job(
            "run_execution_task", execution_id, _job_id=f"execution:{execution_id}"
        )

    async with async_session() as session:
        await receive_channel(
            source=source,
            session=session,
            enqueue=enqueue,
            continue_on_error=True,
        )


def _build_channel_poll_job(
    definition: ChannelDefinition,
) -> WorkerCoroutine:
    """Bind one registered source to an ARQ-compatible polling coroutine."""

    async def poll_channel_job(
        ctx: dict[Any, Any], *args: object, **kwargs: object
    ) -> None:
        """Poll the channel captured by the registry job factory."""
        await poll_registered_channel(
            ctx,
            definition.source,
            *args,
            **kwargs,
        )

    poll_channel_job.__name__ = f"poll_{definition.source.value}_channel"
    return poll_channel_job


_CHANNEL_POLL_JOBS = tuple(
    (
        _build_channel_poll_job(definition),
        set(definition.poll_seconds or ()),
        f"poll_{definition.source.value}_channel",
    )
    for definition in polling_channel_definitions()
)


async def reap_stuck_executions(
    ctx: dict[Any, Any], *args: object, **kwargs: object
) -> None:
    """Reap executions stuck in RUNNING, and re-enqueue stale CREATED ones.

    Args:
        ctx: ARQ job context.
        args: Unused positional arguments (ARQ coroutine protocol).
        kwargs: Unused keyword arguments (ARQ coroutine protocol).

    """
    del args, kwargs
    redis: ArqRedis = ctx["redis"]

    async def re_enqueue(execution_id: int, job_id: str) -> None:
        """Re-enqueue the execution job, deduplicated by execution ID."""
        await redis.enqueue_job("run_execution_task", execution_id, _job_id=job_id)

    async with async_session() as session:
        reaped = await ExecutionUsecase().reap_stuck_executions(
            session=session, re_enqueue=re_enqueue
        )
    if reaped:
        logger.warning("Reaped %s stuck execution(s)", reaped)


async def startup(ctx: dict[Any, Any]) -> None:
    """Configure logging and error tracking when the worker starts.

    Args:
        ctx: ARQ job context.

    """
    del ctx
    configure_logging()
    init_sentry(component="worker")
    await artifact_store.ensure_bucket()


async def cleanup_expired_artifacts(*args: object, **kwargs: object) -> None:
    """Delete one bounded batch of artifacts past their retention deadline."""
    del args, kwargs
    async with async_session() as session:
        cleaned = await ArtifactUsecase(
            store=artifact_store, settings=artifact_settings
        ).cleanup_expired(session=session)
    if cleaned:
        logger.info("Deleted %s expired artifact(s)", cleaned)


class WorkerSettings:
    """ARQ worker configuration."""

    functions: ClassVar[list] = [
        run_execution_task,
        ingest_document_task,
        pull_ollama_model_task,
    ]
    cron_jobs: ClassVar[list] = [
        cron(reap_stuck_executions, minute=_REAPER_MINUTES),
        *(
            cron(job, name=name, second=seconds)
            for job, seconds, name in _CHANNEL_POLL_JOBS
        ),
        cron(cleanup_expired_artifacts, minute=_ARTIFACT_GC_MINUTES),
    ]
    redis_settings = redis_settings.arq
    on_startup = startup
    allow_abort_jobs = True
    # Model pulls can download several GB; give jobs an hour rather than the
    # 5-minute default so a large pull isn't killed mid-download.
    job_timeout = 3600
