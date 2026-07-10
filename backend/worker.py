"""ARQ worker for background workflow execution."""

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar

from arq import cron

from db.repositories import (
    ExecutionRepository,
    NodeRepository,
    TelegramBotRepository,
    WorkflowRepository,
)
from enums import ExecutionStatus, InputNodeFormat, NodeType, OutputNodeFormat
from exceptions import BaseError, TelegramAPIError
from integrations.telegram import get_updates, send_message
from logging_config import configure_logging
from rag.qdrant import get_qdrant_client
from schemas import ExecutionCreate, ExecutionInputPayload
from sessions import async_session
from settings import redis_settings
from streaming import publish_token, publish_token_reset
from usecases import ExecutionUsecase, VectorUsecase
from utils.encryption import decrypt

if TYPE_CHECKING:
    from arq import ArqRedis
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import Node, TelegramBot

logger = logging.getLogger(__name__)

EnqueueCallback = Callable[[int], Awaitable[None]]

# Reap stuck executions every 5 minutes.
_REAPER_MINUTES = set(range(0, 60, 5))
# Short-poll Telegram for new messages every 10 seconds.
_TELEGRAM_POLL_SECONDS = set(range(0, 60, 10))


async def run_execution_task(ctx: dict[Any, Any], execution_id: int) -> None:
    """Run a workflow execution by ID on the worker.

    Args:
        ctx: ARQ job context.
        execution_id: The execution to run.

    """
    logger.info("Running execution %s", execution_id)
    redis: Redis = ctx["redis"]

    async def token_publisher(exec_id: int, node_id: int, delta: str) -> None:
        """Publish a node token delta to the execution's stream channel."""
        await publish_token(redis, exec_id, node_id, delta)

    async def token_reset_publisher(exec_id: int, node_id: int) -> None:
        """Signal a node retry so clients discard its already-streamed text."""
        await publish_token_reset(redis, exec_id, node_id)

    async with async_session() as session:
        await ExecutionUsecase().run_execution(
            session=session,
            execution_id=execution_id,
            session_factory=async_session,
            token_publisher=token_publisher,
            token_reset_publisher=token_reset_publisher,
        )
        await _reply_via_telegram(session=session, execution_id=execution_id)


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


async def _reply_via_telegram(session: "AsyncSession", execution_id: int) -> None:
    """Send a finished execution's result back to Telegram, if configured to.

    The workflow's Output node must have ``format=telegram`` and a
    ``telegram_bot_id`` set. The destination chat is either the Output node's
    own pinned ``telegram_chat_id`` (so this also works for manual, non-
    Telegram-triggered runs) or, absent that, the chat that triggered the run.
    Best-effort: a Telegram delivery failure must not surface as a failure of
    an already-completed execution.

    Args:
        session: Database session.
        execution_id: The finished execution.

    """
    execution = await ExecutionRepository().get_by(session=session, id=execution_id)
    if execution is None:
        return

    output_node = await NodeRepository().get_by(
        session=session, workflow_id=execution.workflow_id, type=NodeType.OUTPUT
    )
    if output_node is None:
        return

    if output_node.data.get("format") != OutputNodeFormat.TELEGRAM.value:
        return

    bot = await _resolve_telegram_bot(session=session, node_data=output_node.data)
    if bot is None:
        return

    chat_id = _resolve_reply_chat_id(
        node_data=output_node.data, triggered_chat_id=execution.telegram_chat_id
    )
    if chat_id is None:
        return

    if execution.status is ExecutionStatus.SUCCESS:
        output = execution.output_data or {}
        text = output.get("value", "") if isinstance(output, dict) else ""
    elif execution.status is ExecutionStatus.FAILED:
        text = f"Execution failed: {execution.error or 'unknown error'}"
    else:
        return

    try:
        await send_message(
            bot_token=decrypt(bot.bot_token),
            chat_id=chat_id,
            text=text or "(empty output)",
        )
    except TelegramAPIError:
        logger.exception(
            "Failed to deliver Telegram reply for execution %s", execution_id
        )


def _resolve_reply_chat_id(
    node_data: dict[str, Any], triggered_chat_id: int | None
) -> int | None:
    """Pick the chat to reply to: a pinned chat ID, else the triggering chat.

    Args:
        node_data: The Output node's configuration data.
        triggered_chat_id: The chat that triggered this run via Telegram
            polling, if any.

    Returns:
        The chat ID to reply to, or ``None`` if neither is available.

    """
    pinned_chat_id = node_data.get("telegram_chat_id")
    if isinstance(pinned_chat_id, int):
        return pinned_chat_id

    return triggered_chat_id


async def _resolve_telegram_bot(
    session: "AsyncSession", node_data: dict[str, Any]
) -> "TelegramBot | None":
    """Look up the Telegram bot referenced by a node's ``telegram_bot_id`` field.

    Args:
        session: Database session.
        node_data: The node's configuration data.

    Returns:
        The bot, or ``None`` if unreferenced or since deleted.

    """
    bot_id = node_data.get("telegram_bot_id")
    if not isinstance(bot_id, int):
        return None

    return await TelegramBotRepository().get_by(session=session, id=bot_id)


async def poll_telegram_updates(
    ctx: dict[Any, Any], *args: object, **kwargs: object
) -> None:
    """Poll every enabled Telegram bot and enqueue executions for new messages.

    Every workflow whose Input node has ``format=telegram`` and references a
    polled bot gets one execution per new message sent to that bot.

    Args:
        ctx: ARQ job context.
        args: Unused positional arguments (ARQ coroutine protocol).
        kwargs: Unused keyword arguments (ARQ coroutine protocol).

    """
    del args, kwargs
    redis: ArqRedis = ctx["redis"]
    telegram_bot_repository = TelegramBotRepository()
    node_repository = NodeRepository()

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await redis.enqueue_job(
            "run_execution_task", execution_id, _job_id=f"execution:{execution_id}"
        )

    async with async_session() as session:
        bots = await telegram_bot_repository.get_all(session=session, enabled=True)
        input_nodes = await node_repository.get_all(
            session=session, type=NodeType.INPUT
        )

        for bot in bots:
            triggered_nodes = _nodes_triggered_by(bot=bot, input_nodes=input_nodes)
            if not triggered_nodes:
                continue

            messages, max_update_id = await _fetch_new_messages(bot=bot)
            if messages is None:
                continue

            for node in triggered_nodes:
                await _trigger_executions(
                    session=session, node=node, messages=messages, enqueue=enqueue
                )

            if max_update_id != bot.last_update_id:
                await telegram_bot_repository.update_by(
                    session=session,
                    data={"last_update_id": max_update_id},
                    id=bot.id,
                )
                await session.commit()


def _nodes_triggered_by(bot: "TelegramBot", input_nodes: list["Node"]) -> list["Node"]:
    """Filter Input nodes wired to poll a given bot.

    Args:
        bot: The Telegram bot.
        input_nodes: All Input nodes across every workflow.

    Returns:
        The Input nodes with ``format=telegram`` referencing this bot.

    """
    return [
        node
        for node in input_nodes
        if node.data.get("format") == InputNodeFormat.TELEGRAM.value
        and node.data.get("telegram_bot_id") == bot.id
    ]


async def _fetch_new_messages(
    bot: "TelegramBot",
) -> tuple[list[tuple[int, str]] | None, int]:
    """Fetch and parse new messages for a bot since its last poll offset.

    Args:
        bot: The Telegram bot to poll.

    Returns:
        A ``(messages, max_update_id)`` tuple. ``messages`` is ``None`` if the
        poll request itself failed (offset should then stay put).

    """
    try:
        updates = await get_updates(
            bot_token=decrypt(bot.bot_token), offset=bot.last_update_id + 1
        )
    except TelegramAPIError:
        logger.exception("Failed to poll Telegram updates for bot %s", bot.id)
        return None, bot.last_update_id

    max_update_id = bot.last_update_id
    messages: list[tuple[int, str]] = []
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            max_update_id = max(max_update_id, update_id)

        chat_id, text = _extract_message(update)
        if chat_id is not None and text:
            messages.append((chat_id, text))

    return messages, max_update_id


async def _trigger_executions(
    session: "AsyncSession",
    node: "Node",
    messages: list[tuple[int, str]],
    enqueue: EnqueueCallback,
) -> None:
    """Create one execution per new message for a Telegram-triggered Input node.

    Args:
        session: Database session.
        node: The triggered Input node.
        messages: ``(chat_id, text)`` pairs fetched for the node's bot.
        enqueue: Callback that schedules an execution for background running.

    """
    workflow = await WorkflowRepository().get_by(session=session, id=node.workflow_id)
    if workflow is None:
        return

    execution_usecase = ExecutionUsecase()
    for chat_id, text in messages:
        try:
            await execution_usecase.create_execution(
                session=session,
                user_id=workflow.owner_id,
                data=ExecutionCreate(
                    workflow_id=node.workflow_id,
                    input_data=ExecutionInputPayload(value=text),
                ),
                enqueue=enqueue,
                telegram_chat_id=chat_id,
            )
        except BaseError:
            logger.exception(
                "Failed to create execution from Telegram message for workflow %s",
                node.workflow_id,
            )


def _extract_message(update: dict[str, Any]) -> tuple[int | None, str | None]:
    """Pull a chat ID and text out of a Telegram update, if present.

    Args:
        update: A raw Telegram update object.

    Returns:
        A ``(chat_id, text)`` tuple, either side ``None`` when absent/malformed.

    """
    message = update.get("message")
    if not isinstance(message, dict):
        return None, None

    text = message.get("text")
    chat = message.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None

    if not isinstance(text, str) or not text or not isinstance(chat_id, int):
        return None, None

    return chat_id, text


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

    async def re_enqueue(execution_id: int) -> None:
        """Re-enqueue the execution job, deduplicated by execution ID."""
        await redis.enqueue_job(
            "run_execution_task", execution_id, _job_id=f"execution:{execution_id}"
        )

    async with async_session() as session:
        reaped = await ExecutionUsecase().reap_stuck_executions(
            session=session, re_enqueue=re_enqueue
        )
    if reaped:
        logger.warning("Reaped %s stuck execution(s)", reaped)


async def startup(ctx: dict[Any, Any]) -> None:
    """Configure logging when the worker starts.

    Args:
        ctx: ARQ job context.

    """
    del ctx
    configure_logging()


class WorkerSettings:
    """ARQ worker configuration."""

    functions: ClassVar[list] = [run_execution_task, ingest_document_task]
    cron_jobs: ClassVar[list] = [
        cron(reap_stuck_executions, minute=_REAPER_MINUTES),
        cron(poll_telegram_updates, second=_TELEGRAM_POLL_SECONDS),
    ]
    redis_settings = redis_settings.arq
    on_startup = startup
