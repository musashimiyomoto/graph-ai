"""ARQ worker for background workflow execution."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from arq import cron
from croniter import CroniterError, croniter

from api.metrics import record_execution
from constants import DEFAULT_TIMEOUT
from db.repositories import (
    EmailAccountRepository,
    ExecutionRepository,
    NodeRepository,
    NodeScheduleRepository,
    TelegramBotRepository,
    WorkflowRepository,
)
from enums import (
    ExecutionSource,
    ExecutionStatus,
    InputNodeFormat,
    NodeType,
    OutputNodeFormat,
)
from exceptions import (
    BaseError,
    EmailConnectionError,
    TelegramAPIError,
    WebhookConnectionError,
)
from integrations.email import (
    EmailConnectionConfig,
    InboundEmail,
    fetch_messages,
    send_email,
)
from integrations.telegram import get_updates, send_message
from integrations.webhook import send_webhook
from llm.ollama import OllamaClient
from logging_config import configure_logging
from observability import init_sentry
from rag.qdrant import get_qdrant_client
from schemas import ExecutionCreate, ExecutionInputPayload
from sessions import async_session
from settings import redis_settings
from streaming import publish_pull_progress, publish_token, publish_token_reset
from usecases import ExecutionTrigger, ExecutionUsecase, VectorUsecase
from utils.encryption import decrypt

if TYPE_CHECKING:
    from arq import ArqRedis
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import EmailAccount, Node, NodeSchedule, TelegramBot
    from schemas import ExecutionResponse

logger = logging.getLogger(__name__)

EnqueueCallback = Callable[[int], Awaitable[None]]

# Reap stuck executions every 5 minutes.
_REAPER_MINUTES = set(range(0, 60, 5))
# Short-poll Telegram for new messages every 10 seconds.
_TELEGRAM_POLL_SECONDS = set(range(0, 60, 10))
# Email polling opens an IMAP connection per active account, so keep it less
# frequent than Telegram's lightweight HTTP short poll.
_EMAIL_POLL_SECONDS = set(range(0, 60, 30))
# Poll cron schedules twice a minute — cron's finest granularity is 1 minute,
# so this keeps a due schedule's fire latency under 30 seconds without
# polling much more often than that granularity warrants.
_SCHEDULE_POLL_SECONDS = set(range(0, 60, 30))


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
        result = await ExecutionUsecase().run_execution(
            session=session,
            execution_id=execution_id,
            session_factory=async_session,
            token_publisher=token_publisher,
            token_reset_publisher=token_reset_publisher,
        )
        await _reply_via_telegram(session=session, execution_id=execution_id)
        await _reply_via_email(session=session, execution_id=execution_id)
        await _deliver_via_webhook(session=session, execution_id=execution_id)

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


def _email_config(account: "EmailAccount") -> EmailConnectionConfig:
    """Build decrypted integration config from a persisted account."""
    return EmailConnectionConfig(
        email_address=account.email_address,
        username=account.username,
        password=decrypt(account.password),
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_use_ssl=account.imap_use_ssl,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_use_tls=account.smtp_use_tls,
        smtp_use_ssl=account.smtp_use_ssl,
    )


def _email_reply_subject(configured: object, triggered: str | None) -> str:
    """Resolve a fixed subject or derive a conventional reply subject."""
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    if triggered:
        return triggered if triggered.lower().startswith("re:") else f"Re: {triggered}"
    return "Workflow result"


async def _reply_via_email(session: "AsyncSession", execution_id: int) -> None:
    """Deliver a finished execution through an email-formatted Output node."""
    execution_repository = ExecutionRepository()
    execution = await execution_repository.get_by(session=session, id=execution_id)
    if execution is None:
        return

    output_node = await NodeRepository().get_by(
        session=session, workflow_id=execution.workflow_id, type=NodeType.OUTPUT
    )
    if output_node is None or output_node.data.get("format") != OutputNodeFormat.EMAIL:
        return

    workflow = await WorkflowRepository().get_by(
        session=session, id=execution.workflow_id
    )
    account_id = output_node.data.get("email_account_id")
    if workflow is None or not isinstance(account_id, int):
        return
    account = await EmailAccountRepository().get_by(
        session=session, id=account_id, user_id=workflow.owner_id
    )
    if account is None:
        return

    configured_recipient = output_node.data.get("email_to")
    recipient = (
        configured_recipient.strip()
        if isinstance(configured_recipient, str) and configured_recipient.strip()
        else execution.email_reply_to
    )
    if not recipient:
        return

    if execution.status is ExecutionStatus.SUCCESS:
        output = execution.output_data or {}
        text = output.get("value", "") if isinstance(output, dict) else ""
    elif execution.status is ExecutionStatus.FAILED:
        text = f"Execution failed: {execution.error or 'unknown error'}"
    else:
        return

    try:
        await send_email(
            config=_email_config(account),
            recipient=recipient,
            subject=_email_reply_subject(
                output_node.data.get("email_subject"), execution.email_subject
            ),
            text=text or "(empty output)",
        )
    except EmailConnectionError:
        logger.exception("Failed to deliver email reply for execution %s", execution_id)


async def _deliver_via_webhook(session: "AsyncSession", execution_id: int) -> None:
    """POST a finished execution to a webhook-formatted Output node."""
    execution = await ExecutionRepository().get_by(session=session, id=execution_id)
    if execution is None:
        return

    output_node = await NodeRepository().get_by(
        session=session, workflow_id=execution.workflow_id, type=NodeType.OUTPUT
    )
    if (
        output_node is None
        or output_node.data.get("format") != OutputNodeFormat.WEBHOOK
    ):
        return

    url = output_node.data.get("webhook_url")
    if not isinstance(url, str) or not url.strip():
        return

    try:
        await send_webhook(
            url=url.strip(),
            payload={
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": execution.status.value,
                "output": execution.output_data,
                "error": execution.error,
            },
        )
    except WebhookConnectionError:
        logger.exception(
            "Failed to deliver webhook result for execution %s", execution_id
        )


def _email_nodes_triggered_by(
    account: "EmailAccount", input_nodes: list["Node"]
) -> list["Node"]:
    """Filter email Input nodes that reference an account."""
    return [
        node
        for node in input_nodes
        if node.data.get("format") == InputNodeFormat.EMAIL
        and node.data.get("email_account_id") == account.id
    ]


def _email_input_value(message: InboundEmail) -> str:
    """Compose subject and body into the engine's text input contract."""
    value = (
        f"Subject: {message.subject}\n\n{message.body}"
        if message.subject
        else message.body
    )
    return value[:50_000]


async def _trigger_email_executions(
    session: "AsyncSession",
    account: "EmailAccount",
    node: "Node",
    messages: list[InboundEmail],
    enqueue: EnqueueCallback,
) -> None:
    """Create one execution per incoming email for one Input node."""
    workflow = await WorkflowRepository().get_by(session=session, id=node.workflow_id)
    if workflow is None or workflow.owner_id != account.user_id:
        return

    usecase = ExecutionUsecase()
    for message in messages:
        if not message.sender:
            continue
        try:
            await usecase.create_execution(
                session=session,
                user_id=workflow.owner_id,
                data=ExecutionCreate(
                    workflow_id=node.workflow_id,
                    input_data=ExecutionInputPayload(value=_email_input_value(message)),
                ),
                enqueue=enqueue,
                trigger=ExecutionTrigger(
                    source=ExecutionSource.EMAIL,
                    email_reply_to=message.sender,
                    email_subject=message.subject,
                ),
            )
        except BaseError:
            logger.exception(
                "Failed to create execution from email for workflow %s",
                node.workflow_id,
            )


async def poll_email_updates(
    ctx: dict[Any, Any], *args: object, **kwargs: object
) -> None:
    """Poll enabled IMAP accounts and enqueue runs for new messages."""
    del args, kwargs
    redis: ArqRedis = ctx["redis"]

    async def enqueue(execution_id: int) -> None:
        """Enqueue a deduplicated execution job."""
        await redis.enqueue_job(
            "run_execution_task", execution_id, _job_id=f"execution:{execution_id}"
        )

    account_repository = EmailAccountRepository()
    async with async_session() as session:
        accounts = await account_repository.get_all(session=session, enabled=True)
        input_nodes = await NodeRepository().get_all(
            session=session, type=NodeType.INPUT
        )
        for account in accounts:
            nodes = _email_nodes_triggered_by(account, input_nodes)
            if not nodes:
                continue
            try:
                messages = await fetch_messages(
                    config=_email_config(account), last_uid=account.last_uid
                )
            except EmailConnectionError:
                logger.exception("Failed to poll email account %s", account.id)
                continue

            for node in nodes:
                await _trigger_email_executions(
                    session=session,
                    account=account,
                    node=node,
                    messages=messages,
                    enqueue=enqueue,
                )
            if messages:
                await account_repository.update_by(
                    session=session,
                    data={"last_uid": max(message.uid for message in messages)},
                    id=account.id,
                )
                await session.commit()


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
                trigger=ExecutionTrigger(
                    source=ExecutionSource.TELEGRAM, telegram_chat_id=chat_id
                ),
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


async def poll_scheduled_triggers(
    ctx: dict[Any, Any], *args: object, **kwargs: object
) -> None:
    """Fire due cron schedules, enqueuing one execution per due schedule.

    Every Input node with ``format=schedule`` has a ``NodeSchedule`` row
    (kept in sync with the node by ``NodeUsecase._sync_node_schedule``). A
    schedule is due once its cron expression's next boundary after
    ``last_fired_at`` has passed. ``last_fired_at`` is then reset to the
    wall-clock check time (not the matched boundary), so a worker that was
    down across several missed boundaries fires once on wake-up and resumes
    from "now" rather than replaying every boundary it missed — the same
    "skip, don't stack" choice as the stuck-execution reaper, and distinct
    from Telegram's offset-based catch-up (safe to replay: relaying an old
    message costs one extra reply, replaying a missed schedule could mean
    hours of stacked LLM calls).

    Args:
        ctx: ARQ job context.
        args: Unused positional arguments (ARQ coroutine protocol).
        kwargs: Unused keyword arguments (ARQ coroutine protocol).

    """
    del args, kwargs
    redis: ArqRedis = ctx["redis"]
    node_schedule_repository = NodeScheduleRepository()
    node_repository = NodeRepository()
    now = datetime.now(tz=UTC)

    async def enqueue(execution_id: int) -> None:
        """Enqueue the execution job, deduplicated by execution ID."""
        await redis.enqueue_job(
            "run_execution_task", execution_id, _job_id=f"execution:{execution_id}"
        )

    async with async_session() as session:
        schedules = await node_schedule_repository.get_all(session=session)

        for schedule in schedules:
            if not _schedule_is_due(schedule=schedule, now=now):
                continue

            node = await node_repository.get_by(session=session, id=schedule.node_id)
            if node is not None and node.type is NodeType.INPUT:
                await _trigger_scheduled_execution(
                    session=session, node=node, enqueue=enqueue
                )

            await node_schedule_repository.update_by(
                session=session, data={"last_fired_at": now}, id=schedule.id
            )
            await session.commit()


def _schedule_is_due(schedule: "NodeSchedule", now: datetime) -> bool:
    """Return whether a schedule's next cron boundary after its anchor has passed.

    Args:
        schedule: The schedule to check.
        now: The current time.

    Returns:
        Whether the schedule should fire.

    """
    try:
        upcoming = croniter(schedule.cron_expression, schedule.last_fired_at).get_next(
            datetime
        )
    except CroniterError:
        logger.exception(
            "Invalid cron expression for schedule %s; skipping", schedule.id
        )
        return False
    return upcoming <= now


async def _trigger_scheduled_execution(
    session: "AsyncSession",
    node: "Node",
    enqueue: EnqueueCallback,
) -> None:
    """Create one execution for a due scheduled Input node.

    A scheduled run has no incoming message, so it carries the node's fixed
    ``scheduled_value`` text (empty if unset) as its input — same shape as a
    manual run, just triggered by the clock instead of a user click.

    Args:
        session: Database session.
        node: The Input node the schedule fired for.
        enqueue: Callback that schedules an execution for background running.

    """
    workflow = await WorkflowRepository().get_by(session=session, id=node.workflow_id)
    if workflow is None:
        return

    scheduled_value = node.data.get("scheduled_value")
    if not isinstance(scheduled_value, str):
        scheduled_value = ""

    try:
        await ExecutionUsecase().create_execution(
            session=session,
            user_id=workflow.owner_id,
            data=ExecutionCreate(
                workflow_id=node.workflow_id,
                input_data=ExecutionInputPayload(value=scheduled_value),
            ),
            enqueue=enqueue,
            trigger=ExecutionTrigger(source=ExecutionSource.SCHEDULE),
        )
    except BaseError:
        logger.exception(
            "Failed to create scheduled execution for workflow %s", node.workflow_id
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
    """Configure logging and error tracking when the worker starts.

    Args:
        ctx: ARQ job context.

    """
    del ctx
    configure_logging()
    init_sentry(component="worker")


class WorkerSettings:
    """ARQ worker configuration."""

    functions: ClassVar[list] = [
        run_execution_task,
        ingest_document_task,
        pull_ollama_model_task,
    ]
    cron_jobs: ClassVar[list] = [
        cron(reap_stuck_executions, minute=_REAPER_MINUTES),
        cron(poll_telegram_updates, second=_TELEGRAM_POLL_SECONDS),
        cron(poll_email_updates, second=_EMAIL_POLL_SECONDS),
        cron(poll_scheduled_triggers, second=_SCHEDULE_POLL_SECONDS),
    ]
    redis_settings = redis_settings.arq
    on_startup = startup
    allow_abort_jobs = True
    # Model pulls can download several GB; give jobs an hour rather than the
    # 5-minute default so a large pull isn't killed mid-download.
    job_timeout = 3600
