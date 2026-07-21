"""Execution use case implementation."""

import asyncio
import contextlib
import json
import logging
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from db.models import Execution, NodeExecution, WorkflowVersion

from constants import (
    DEFAULT_PAGE_SIZE,
    MAX_LOOP_ITERATIONS,
    MAX_NODE_ATTEMPTS,
    MAX_NODE_OUTPUT_CHARS,
    MAX_WORKFLOW_CALL_DEPTH,
    NODE_TIMEOUT_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
    STREAM_MAX_ITERATIONS,
    STREAM_POLL_SECONDS,
    STUCK_CREATED_TIMEOUT_SECONDS,
    STUCK_EXECUTION_TIMEOUT_SECONDS,
)
from db.repositories import (
    EdgeRepository,
    ExecutionRepository,
    LLMProviderRepository,
    MCPServerRepository,
    NodeExecutionRepository,
    NodeRepository,
    PostgresConnectionRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)
from enums import (
    ConditionType,
    ExecutionSource,
    ExecutionStatus,
    LoopMode,
    NodeType,
    PortCoercion,
)
from exceptions import (
    BaseError,
    ExecutionApprovalNotPendingError,
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotCancellableError,
    ExecutionNotFoundError,
    NodeExecutionTimeoutError,
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from nodes import (
    NodeExecutionContext,
    NodeExecutionResult,
    NodeHandlerDeps,
    NodeHandlerRegistry,
    NodeValue,
    OnToken,
    check_edge_ports,
    coerce_node_value,
    evaluate_condition,
    get_node_definition,
    get_node_output_handles,
    get_node_output_port,
    resolve_wait_until,
    select_switch_handle,
)
from schemas import (
    EdgeResponse,
    ExecutionCreate,
    ExecutionGraphContext,
    ExecutionOutputPayload,
    ExecutionResponse,
    NodeExecutionResponse,
    NodeResponse,
    TokenUsage,
    WorkflowVersionResponse,
)
from streaming import subscribe_tokens
from usecases.audit import AuditEvent, AuditUsecase
from usecases.usage import UsageUsecase

logger = logging.getLogger(__name__)

type _RuntimeEdge = tuple[int, str | None, str | None, PortCoercion | None]

# Publishes a (execution_id, node_id, token delta) for live streaming.
TokenPublisher = Callable[[int, int, str], Awaitable[None]]
# Signals (execution_id, node_id) that a node's stream is restarting (a retry)
# and any previously streamed text for it should be discarded by the client.
TokenResetPublisher = Callable[[int, int], Awaitable[None]]


class _ExecutionPausedError(Exception):
    """Internal control flow raised after a durable checkpoint is committed."""


@dataclass(frozen=True)
class _TokenPublishers:
    """Bundles the token-stream callbacks so they pass through as one param."""

    delta: TokenPublisher | None = None
    reset: TokenResetPublisher | None = None


def _edges_within_scope(
    nodes: list[NodeResponse], edges: list[EdgeResponse]
) -> list[EdgeResponse]:
    """Filter edges to only those whose endpoints are both in `nodes`.

    Edges carry no scope column of their own — a workflow's edges are
    fetched flat by `workflow_id`, same as before Loop existed — but by
    construction an edge only ever connects two nodes in the same scope (a
    loop body's canvas only lets you wire nodes inside that same body). This
    partitions a flat edge list down to one scope without needing a new
    column, and drops (rather than errors on) an edge whose endpoint isn't
    in scope, since that's just an edge belonging to a *different* scope.

    Args:
        nodes: The nodes in this scope.
        edges: The workflow's full edge list (all scopes).

    Returns:
        Only the edges whose source and target are both in `nodes`.

    """
    node_ids = {node.id for node in nodes}
    return [
        edge
        for edge in edges
        if edge.source_node_id in node_ids and edge.target_node_id in node_ids
    ]


def _truncate_for_storage(output: str | None) -> str | None:
    """Cap a node's output before persisting it, with a visible marker.

    Bounds `node_executions.output` storage (e.g. against a giant scraped
    page or LLM response) without touching the in-memory value fed to
    downstream nodes — only what's recorded for display/debugging.
    """
    if output is None or len(output) <= MAX_NODE_OUTPUT_CHARS:
        return output
    return f"{output[:MAX_NODE_OUTPUT_CHARS]}\n\n[truncated: {len(output)} chars total]"


def _join_text_values(values: list[NodeValue], separator: str = "\n") -> str:
    """Join typed text values at an explicitly text-only engine boundary."""
    return separator.join(value.require_text() for value in values)


@dataclass(frozen=True)
class _GraphSource:
    """A workflow's full node/edge list, across every scope.

    Unlike an `ExecutionGraphContext` (always scoped to one graph — the
    top-level graph, or one Loop node's body), this is the raw material both
    are built from: whichever source the run is pinned to (the live DB, or a
    `WorkflowVersion` snapshot), loaded once. The recursive loop runner
    partitions this by `parent_node_id` on demand to build a body's own
    `ExecutionGraphContext`, without a second DB round-trip and without
    caring whether the run is live or replaying a pinned snapshot.
    """

    all_nodes: list[NodeResponse]
    all_edges: list[EdgeResponse]


@dataclass(frozen=True)
class _LoadedGraph:
    """The top-level graph an execution runs, bundled with its full source.

    What `_load_graph`/`_build_graph_from_snapshot`/`_load_execution_graph`
    hand back — one param instead of two everywhere it's threaded through.
    """

    top_level: ExecutionGraphContext
    source: _GraphSource
    called_graphs: dict[int, "_LoadedGraph"]


@dataclass(frozen=True)
class _NodeRunContext:
    """Loop-invariant context shared across node executions in one run."""

    execution_id: int
    workflow_id: int
    workflow_owner_id: int
    input_value: NodeValue
    graph_source: _GraphSource
    called_graphs: dict[int, _LoadedGraph]
    workflow_call_stack: tuple[int, ...]
    token_publisher: TokenPublisher | None = None
    token_reset_publisher: TokenResetPublisher | None = None


@dataclass(frozen=True)
class _WaveState:
    """Per-node bookkeeping accumulated across waves.

    The dataclass itself is frozen, but its dict fields are mutated in place
    as nodes resolve — this just bundles them as one parameter.
    """

    outputs_by_node: dict[int, NodeValue]
    named_outputs_by_node: dict[int, dict[str, NodeValue]]
    live_by_node: dict[int, bool]
    selected_handle_by_node: dict[int, str | None]
    resolved_by_node: dict[int, "NodeExecution"]


@dataclass(frozen=True)
class _NodeOutcome:
    """Final result of a single node execution."""

    status: ExecutionStatus
    output: NodeValue | None = None
    outputs: dict[str, NodeValue] | None = None
    error: str | None = None
    iteration: int | None = None
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class _Adjacency:
    """Sorted graph adjacency, with per-edge source handles, plus indegree."""

    outbound: dict[int, list[int]]
    inbound: dict[int, list[int]]
    outbound_edges: dict[int, list[_RuntimeEdge]]
    inbound_edges: dict[int, list[_RuntimeEdge]]
    indegree: dict[int, int]


@dataclass(frozen=True)
class ExecutionTrigger:
    """Internal-only metadata about what triggered an execution.

    Never set by the public API. Channel pollers attach the address/chat needed
    to deliver the finished result back to the triggering conversation.
    """

    source: ExecutionSource = ExecutionSource.MANUAL
    telegram_chat_id: int | None = None
    email_reply_to: str | None = None
    email_subject: str | None = None


@dataclass(frozen=True)
class ExecutionListFilter:
    """Filter for listing a workflow's executions."""

    workflow_id: int
    # None matches any source; a non-empty list restricts to those sources
    # (e.g. Activity Log showing Telegram + schedule together, distinct from
    # the owner's own manual test runs).
    source: list[ExecutionSource] | None = None


class ExecutionUsecase:
    """Execution business logic."""

    _max_node_attempts: int = MAX_NODE_ATTEMPTS
    _node_timeout_seconds: float = NODE_TIMEOUT_SECONDS
    _max_loop_iterations: int = MAX_LOOP_ITERATIONS

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._execution_repository = ExecutionRepository()
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._edge_repository = EdgeRepository()
        self._node_execution_repository = NodeExecutionRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._postgres_connection_repository = PostgresConnectionRepository()
        self._mcp_server_repository = MCPServerRepository()
        self._workflow_version_repository = WorkflowVersionRepository()
        self._node_registry = NodeHandlerRegistry(
            NodeHandlerDeps(
                llm_provider_repository=self._llm_provider_repository,
                postgres_connection_repository=self._postgres_connection_repository,
                mcp_server_repository=self._mcp_server_repository,
            )
        )
        self._usage_usecase = UsageUsecase()
        self._audit_usecase = AuditUsecase()

    async def create_execution(
        self,
        session: AsyncSession,
        user_id: int,
        data: ExecutionCreate,
        enqueue: Callable[[int], Awaitable[None]],
        trigger: ExecutionTrigger | None = None,
    ) -> ExecutionResponse:
        """Validate a workflow, persist a queued execution, and enqueue it.

        The graph is validated synchronously so invalid workflows fail fast with a
        4xx before any background work is scheduled. The actual run happens on a
        worker via ``run_execution``.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The execution payload.
            enqueue: Callback that schedules the execution for background running.
            trigger: Internal source and reply metadata for channel-triggered runs.

        Returns:
            The created execution in ``CREATED`` (queued) state.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            ExecutionGraphValidationError: If graph is invalid for execution.

        """
        trigger = trigger or ExecutionTrigger()
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=data.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        # Reject up front if the tenant is already at a configured daily limit,
        # before snapshotting the graph or scheduling any background work.
        await self._usage_usecase.check_quota(session=session, user_id=user_id)

        # Pin the run to an immutable graph snapshot: either a requested past
        # version, or a fresh snapshot of the current live graph (deduped).
        if data.version_id is not None:
            version = await self._workflow_version_repository.get_by(
                session=session, id=data.version_id, workflow_id=data.workflow_id
            )
            if version is None:
                raise WorkflowVersionNotFoundError
        else:
            version = await self._snapshot_workflow(
                session=session,
                workflow_id=data.workflow_id,
                owner_id=user_id,
            )

        # Validate the snapshot up front (fail-fast); the worker reuses it at run time.
        self._build_graph_from_snapshot(version.graph)

        execution = await self._execution_repository.create(
            session=session,
            data={
                "workflow_id": data.workflow_id,
                "version_id": version.id,
                "input_data": data.input_data.model_dump(),
                "status": ExecutionStatus.CREATED,
                "source": trigger.source,
                "telegram_chat_id": trigger.telegram_chat_id,
                "email_reply_to": trigger.email_reply_to,
                "email_subject": trigger.email_subject,
            },
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="execution.create",
                entity_type="execution",
                entity_id=execution.id,
                metadata={
                    "workflow_id": data.workflow_id,
                    "source": trigger.source.value,
                },
            ),
        )
        await session.commit()

        await enqueue(execution.id)

        return await self.get_execution(
            session=session, execution_id=execution.id, user_id=user_id
        )

    async def run_execution(
        self,
        session: AsyncSession,
        execution_id: int,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        token_publisher: TokenPublisher | None = None,
        token_reset_publisher: TokenResetPublisher | None = None,
    ) -> ExecutionResponse:
        """Run a queued execution to completion (worker entry point).

        Args:
            session: The session (owned by the worker, not the request).
            execution_id: The execution to run.
            session_factory: When provided, independent graph branches run
                concurrently, each node on its own session. When ``None``, nodes
                run serially on ``session``.
            token_publisher: When provided, LLM nodes stream token deltas through
                it for live client streaming.
            token_reset_publisher: When provided, called before a node's retry
                so clients can discard that node's already-streamed text.

        Returns:
            The finalized execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not found.
            ExecutionGraphValidationError: If graph is invalid for execution.

        """
        execution = await self._prepare_execution_for_run(
            session=session, execution_id=execution_id
        )
        if execution.status is ExecutionStatus.WAITING_DELAY:
            return ExecutionResponse.model_validate(execution)

        workflow = await self._workflow_repository.get_by(
            session=session, id=execution.workflow_id
        )
        if workflow is None:
            raise WorkflowNotFoundError
        workflow_owner_id = workflow.owner_id

        claimed = await self._claim_execution(
            session=session,
            execution=execution,
        )
        if not claimed:
            # Already claimed or finalized (e.g. duplicate delivery); do not re-run.
            current = await self._execution_repository.get_by(
                session=session, id=execution_id
            )
            if current is None:
                raise ExecutionNotFoundError
            return ExecutionResponse.model_validate(current)

        loaded_graph = await self._load_execution_graph(
            session=session, execution=execution
        )

        try:
            output_data = await self._run_execution(
                session=session,
                execution_id=execution_id,
                loaded_graph=loaded_graph,
                session_factory=session_factory,
                token_publishers=_TokenPublishers(
                    delta=token_publisher, reset=token_reset_publisher
                ),
            )
        except _ExecutionPausedError:
            logger.info("Execution %s reached a durable checkpoint", execution_id)
            await session.rollback()
        except BaseError as exc:
            logger.warning("Execution %s failed: %s", execution_id, exc.message)
            await session.rollback()
            await self._mark_execution_failed(
                session=session, execution_id=execution_id, error=exc.message
            )
        except Exception:
            logger.exception("Execution %s failed with unexpected error", execution_id)
            await session.rollback()
            await self._mark_execution_failed(
                session=session,
                execution_id=execution_id,
                error="Internal execution error",
            )
        else:
            await self._mark_execution_success(
                session=session, execution_id=execution_id, output_data=output_data
            )

        finalized = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if finalized is None:
            raise ExecutionNotFoundError

        # Snapshot the response before touching usage: record_run commits,
        # which expires the ORM object and would make a later attribute read
        # trigger a lazy reload outside the async context.
        response = ExecutionResponse.model_validate(finalized)

        await self._record_finalized_usage(
            session=session,
            execution=response,
            user_id=workflow_owner_id,
        )

        return response

    async def _claim_execution(
        self,
        session: AsyncSession,
        execution: "Execution",
    ) -> bool:
        """Atomically claim a queued execution while preserving resume timing."""
        claim_time = datetime.now(tz=UTC)
        claim_data: dict[str, object] = {
            "status": ExecutionStatus.RUNNING,
            "heartbeat_at": claim_time,
        }
        if execution.heartbeat_at is None:
            claim_data["started_at"] = claim_time
        return await self._execution_repository.update_status_if(
            session=session,
            execution_id=execution.id,
            expected_status=ExecutionStatus.CREATED,
            data=claim_data,
        )

    async def _prepare_execution_for_run(
        self,
        session: AsyncSession,
        execution_id: int,
    ) -> "Execution":
        """Load an execution and resume its Delay checkpoint when due."""
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if execution is None:
            raise ExecutionNotFoundError
        if execution.status is not ExecutionStatus.WAITING_DELAY:
            return execution

        await self._resume_due_delays(session=session, execution_id=execution_id)
        current = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if current is None:
            raise ExecutionNotFoundError
        return current

    async def _resume_due_delays(
        self,
        session: AsyncSession,
        execution_id: int,
    ) -> bool:
        """Complete due Delay checkpoints and make their execution claimable."""
        execution = await self._execution_repository.get_by_id_for_update(
            session=session, execution_id=execution_id
        )
        if execution is None:
            raise ExecutionNotFoundError
        now = datetime.now(tz=UTC)
        if (
            execution.status is not ExecutionStatus.WAITING_DELAY
            or execution.wait_until is None
            or execution.wait_until > now
        ):
            await session.rollback()
            return False

        waiting = await self._node_execution_repository.get_all(
            session=session,
            execution_id=execution_id,
            status=ExecutionStatus.WAITING_DELAY,
        )
        due = [
            node_execution
            for node_execution in waiting
            if node_execution.wait_until is not None
            and node_execution.wait_until <= now
        ]
        if not due:
            await session.rollback()
            return False

        for node_execution in due:
            await self._node_execution_repository.update_by(
                session=session,
                id=node_execution.id,
                data={
                    "status": ExecutionStatus.SUCCESS,
                    "finished_at": now,
                },
            )
        await self._execution_repository.update_by(
            session=session,
            id=execution_id,
            data={
                "status": ExecutionStatus.CREATED,
                "wait_until": None,
                "heartbeat_at": now,
            },
        )
        await session.commit()
        return True

    async def _record_finalized_usage(
        self,
        session: AsyncSession,
        execution: ExecutionResponse,
        user_id: int,
    ) -> None:
        """Record usage for a worker-finalized execution.

        Args:
            session: The worker session.
            execution: The durable terminal execution snapshot.
            user_id: The workflow owner.

        """
        # Cancellation records usage in the request that wins the terminal CAS.
        # If an ARQ abort arrives late and this coroutine continues, do not count
        # that same run a second time.
        if execution.status in {
            ExecutionStatus.WAITING_APPROVAL,
            ExecutionStatus.WAITING_DELAY,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
        }:
            return

        try:
            await self._usage_usecase.record_run(
                session=session,
                user_id=user_id,
                total_tokens=execution.total_tokens or 0,
            )
            await session.commit()
        except Exception:
            logger.exception("Failed to record usage for execution %s", execution.id)
            await session.rollback()

    async def reap_stuck_executions(
        self,
        session: AsyncSession,
        older_than_seconds: int = STUCK_EXECUTION_TIMEOUT_SECONDS,
        created_older_than_seconds: int = STUCK_CREATED_TIMEOUT_SECONDS,
        re_enqueue: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> int:
        """Mark executions stuck in RUNNING beyond the timeout as FAILED.

        Staleness is measured from ``heartbeat_at`` (bumped each time a node
        completes), not ``started_at`` — a long multi-node run that's still
        making progress keeps refreshing its heartbeat and won't be reaped
        just for having run for a while. Falls back to ``started_at`` for a
        run that hasn't completed a single node yet.

        Also re-enqueues executions stuck in ``CREATED`` beyond a much
        shorter timeout, plus due ``WAITING_DELAY`` checkpoints whose deferred
        Redis job may have been lost after the database commit.
        Re-enqueuing rather than failing them is safe: the worker's job
        dedup (``_job_id=f"execution:{id}"``) makes a duplicate enqueue for
        an execution that's actually already queued/running a no-op.

        Args:
            session: The session.
            older_than_seconds: Minimum time since the last heartbeat to
                consider a RUNNING execution stuck.
            created_older_than_seconds: Minimum time since creation to
                consider a CREATED execution stuck.
            re_enqueue: Callback that re-schedules a stale CREATED execution
                for background running. If ``None``, stale CREATED
                executions are left alone.

        Returns:
            The number of executions reaped (failed RUNNING + re-enqueued
            CREATED).

        """
        now = datetime.now(tz=UTC)
        cutoff = now - timedelta(seconds=older_than_seconds)
        running = await self._execution_repository.get_all(
            session=session, status=ExecutionStatus.RUNNING
        )
        stuck = [
            execution
            for execution in running
            if (execution.heartbeat_at or execution.started_at) < cutoff
        ]
        for execution in stuck:
            logger.warning("Reaping stuck execution %s", execution.id)
            await self._mark_execution_failed(
                session=session,
                execution_id=execution.id,
                error="Execution timed out (worker did not finish)",
            )

        reaped = len(stuck)

        if re_enqueue is not None:
            created_cutoff = now - timedelta(seconds=created_older_than_seconds)
            created = await self._execution_repository.get_all(
                session=session, status=ExecutionStatus.CREATED
            )
            stale_created = [
                execution
                for execution in created
                if execution.started_at < created_cutoff
            ]
            for execution in stale_created:
                logger.warning("Re-enqueuing stale CREATED execution %s", execution.id)
                await re_enqueue(
                    execution.id,
                    execution.queue_job_id or f"execution:{execution.id}",
                )

            reaped += len(stale_created)

            waiting_delays = await self._execution_repository.get_all(
                session=session, status=ExecutionStatus.WAITING_DELAY
            )
            due_delays = [
                execution
                for execution in waiting_delays
                if execution.wait_until is not None and execution.wait_until <= now
            ]
            for execution in due_delays:
                logger.warning("Re-enqueuing due delayed execution %s", execution.id)
                await re_enqueue(
                    execution.id,
                    execution.queue_job_id
                    or f"execution:{execution.id}:delay:{uuid4().hex}",
                )

            reaped += len(due_delays)

        return reaped

    async def _load_graph(
        self, session: AsyncSession, workflow_id: int
    ) -> _LoadedGraph:
        """Build and validate the top-level execution graph for a workflow.

        Scoped to `parent_node_id IS NULL` — nodes inside a Loop node's body
        aren't part of the top-level graph at all; the recursive loop runner
        builds its own scoped `ExecutionGraphContext` per Loop node instead,
        from the `_GraphSource` bundled alongside the top-level context.

        Args:
            session: The session.
            workflow_id: The workflow ID.

        Returns:
            The validated top-level graph, bundled with the workflow's full
            (every-scope) node/edge list it was built from.

        Raises:
            ExecutionGraphValidationError: If graph is invalid for execution.

        """
        all_nodes = [
            NodeResponse.model_validate(node)
            for node in await self._node_repository.get_all(
                session=session, workflow_id=workflow_id
            )
        ]
        all_edges = [
            EdgeResponse.model_validate(edge)
            for edge in await self._edge_repository.get_all(
                session=session, workflow_id=workflow_id
            )
        ]
        graph_source = _GraphSource(all_nodes=all_nodes, all_edges=all_edges)
        top_level = self._build_scoped_graph_context(
            graph_source=graph_source, parent_node_id=None
        )
        return _LoadedGraph(
            top_level=top_level,
            source=graph_source,
            called_graphs={},
        )

    async def _load_execution_graph(
        self, session: AsyncSession, execution: "Execution"
    ) -> _LoadedGraph:
        """Load the graph an execution should run: its pinned snapshot if any.

        Args:
            session: The session.
            execution: The execution ORM row.

        Returns:
            The validated top-level graph, bundled with the workflow's full
            (every-scope) node/edge list it was built from.

        Raises:
            ExecutionGraphValidationError: If the graph is invalid.

        """
        if execution.version_id is not None:
            version = await self._workflow_version_repository.get_by(
                session=session, id=execution.version_id
            )
            if version is not None:
                return self._build_graph_from_snapshot(version.graph)

        # No pinned version (legacy execution) or it was removed: use the live graph.
        return await self._load_graph(
            session=session, workflow_id=execution.workflow_id
        )

    def _build_graph_from_snapshot(self, graph: dict[str, object]) -> _LoadedGraph:
        """Build the graph context from a stored version snapshot.

        Args:
            graph: Snapshot dict with ``nodes`` and ``edges`` lists (every
                scope — a loop body's nodes are dumped flat alongside the
                top-level ones, same as the live graph; see `_GraphSource`).

        Returns:
            The validated top-level graph, bundled with the snapshot's full
            (every-scope) node/edge list it was built from.

        Raises:
            ExecutionGraphValidationError: If the snapshot graph is invalid.

        """
        raw_nodes = graph.get("nodes", [])
        raw_edges = graph.get("edges", [])
        raw_called_workflows = graph.get("called_workflows", {})
        nodes = list(raw_nodes) if isinstance(raw_nodes, list) else []
        edges = list(raw_edges) if isinstance(raw_edges, list) else []
        called_workflows = (
            dict(raw_called_workflows) if isinstance(raw_called_workflows, dict) else {}
        )
        graph_source = _GraphSource(
            all_nodes=[NodeResponse.model_validate(node) for node in nodes],
            all_edges=[EdgeResponse.model_validate(edge) for edge in edges],
        )
        top_level = self._build_scoped_graph_context(
            graph_source=graph_source, parent_node_id=None
        )
        called_graphs: dict[int, _LoadedGraph] = {}
        for raw_workflow_id, called_graph in called_workflows.items():
            if not isinstance(called_graph, dict):
                continue
            try:
                workflow_id = int(raw_workflow_id)
            except (TypeError, ValueError):
                continue
            if workflow_id <= 0:
                continue
            called_graphs[workflow_id] = self._build_graph_from_snapshot(called_graph)
        return _LoadedGraph(
            top_level=top_level,
            source=graph_source,
            called_graphs=called_graphs,
        )

    def _build_scoped_graph_context(
        self, graph_source: _GraphSource, parent_node_id: int | None
    ) -> ExecutionGraphContext:
        """Build one scope's `ExecutionGraphContext` out of a `_GraphSource`.

        `parent_node_id=None` is the top-level graph (entry/exit are
        `INPUT`/`OUTPUT`); any other value is a specific Loop node's body
        (entry/exit are `LOOP_INPUT`/`LOOP_OUTPUT`).

        Args:
            graph_source: The workflow's full (every-scope) node/edge list.
            parent_node_id: The scope to build — `None` for top-level, or a
                Loop node's id for its body.

        Returns:
            The validated graph context for that one scope.

        Raises:
            ExecutionGraphValidationError: If that scope's graph is invalid.

        """
        nodes = [
            node
            for node in graph_source.all_nodes
            if node.parent_node_id == parent_node_id
        ]
        is_top_level = parent_node_id is None
        return self._build_graph_context(
            nodes=nodes,
            edges=_edges_within_scope(nodes=nodes, edges=graph_source.all_edges),
            input_type=NodeType.INPUT if is_top_level else NodeType.LOOP_INPUT,
            output_type=NodeType.OUTPUT if is_top_level else NodeType.LOOP_OUTPUT,
        )

    async def _snapshot_workflow(
        self,
        session: AsyncSession,
        workflow_id: int,
        owner_id: int,
    ) -> "WorkflowVersion":
        """Snapshot the live graph and its called workflows.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            owner_id: Owner of every workflow allowed in the call chain.

        Returns:
            The new or reused workflow version.

        """
        graph = await self._snapshot_graph(
            session=session,
            workflow_id=workflow_id,
            owner_id=owner_id,
            call_stack=(workflow_id,),
        )

        latest_versions = await self._workflow_version_repository.get_all(
            session=session, limit=1, descending=True, workflow_id=workflow_id
        )
        latest = latest_versions[0] if latest_versions else None
        if latest is not None and latest.graph == graph:
            return latest

        next_number = latest.version + 1 if latest is not None else 1
        return await self._workflow_version_repository.create(
            session=session,
            data={
                "workflow_id": workflow_id,
                "version": next_number,
                "graph": graph,
            },
        )

    async def _snapshot_graph(
        self,
        session: AsyncSession,
        workflow_id: int,
        owner_id: int,
        call_stack: tuple[int, ...],
    ) -> dict[str, object]:
        """Build one immutable graph snapshot with its dependency closure.

        Call Workflow nodes are execution dependencies, so the parent version
        embeds each target graph recursively. This keeps queued and pinned
        executions reproducible if a target workflow is edited or deleted
        before the worker runs.

        Args:
            session: Database session.
            workflow_id: Workflow being snapshotted.
            owner_id: Owner required for every referenced workflow.
            call_stack: Workflow IDs from the root through this workflow.

        Returns:
            JSON-serializable graph data.

        Raises:
            ExecutionGraphValidationError: If a target is invalid, missing,
                recursive, foreign, or exceeds the nesting cap.

        """
        nodes = await self._node_repository.get_all(
            session=session, workflow_id=workflow_id
        )
        edges = await self._edge_repository.get_all(
            session=session, workflow_id=workflow_id
        )
        node_responses = [NodeResponse.model_validate(node) for node in nodes]
        called_workflows: dict[str, dict[str, object]] = {}

        for node in node_responses:
            if node.type is not NodeType.CALL_WORKFLOW:
                continue
            target_id = node.data.get("target_workflow_id")
            if not isinstance(target_id, int) or target_id <= 0:
                raise ExecutionGraphValidationError(
                    message="Call Workflow node requires a target workflow"
                )
            if target_id in call_stack:
                chain = " -> ".join(str(item) for item in (*call_stack, target_id))
                raise ExecutionGraphValidationError(
                    message=f"Recursive workflow call detected: {chain}"
                )
            if len(call_stack) >= MAX_WORKFLOW_CALL_DEPTH:
                raise ExecutionGraphValidationError(
                    message=(
                        "Call Workflow nesting exceeds the maximum depth of "
                        f"{MAX_WORKFLOW_CALL_DEPTH}"
                    )
                )
            target = await self._workflow_repository.get_by(
                session=session,
                id=target_id,
                owner_id=owner_id,
            )
            if target is None:
                raise ExecutionGraphValidationError(
                    message="Referenced workflow does not exist"
                )
            key = str(target_id)
            if key not in called_workflows:
                called_workflows[key] = await self._snapshot_graph(
                    session=session,
                    workflow_id=target_id,
                    owner_id=owner_id,
                    call_stack=(*call_stack, target_id),
                )

        return {
            "nodes": [node.model_dump(mode="json") for node in node_responses],
            "edges": [
                EdgeResponse.model_validate(edge).model_dump(mode="json")
                for edge in edges
            ],
            "called_workflows": called_workflows,
        }

    async def get_workflow_versions(
        self, session: AsyncSession, workflow_id: int, user_id: int
    ) -> list[WorkflowVersionResponse]:
        """List a workflow's version snapshots, newest first.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            user_id: The owner user ID.

        Returns:
            The list of version metadata.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return [
            WorkflowVersionResponse.model_validate(version)
            for version in await self._workflow_version_repository.get_all(
                session=session, descending=True, workflow_id=workflow_id
            )
        ]

    async def get_executions(
        self,
        session: AsyncSession,
        user_id: int,
        list_filter: ExecutionListFilter,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> list[ExecutionResponse]:
        """List executions for a workflow, newest first.

        Args:
            session: The session.
            user_id: The owner user ID.
            list_filter: The workflow to list, and optionally restrict to
                executions triggered a specific way (e.g. only the owner's
                manual test runs, or only real Telegram traffic).
            limit: Maximum executions to return.
            offset: Executions to skip (for paging).

        Returns:
            The list of executions.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=list_filter.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        filters: dict[str, object] = {"workflow_id": list_filter.workflow_id}
        if list_filter.source:
            filters["source"] = list_filter.source

        return [
            ExecutionResponse.model_validate(execution)
            for execution in await self._execution_repository.get_all(
                session=session,
                limit=limit,
                offset=offset,
                descending=True,
                **filters,
            )
        ]

    async def get_execution(
        self, session: AsyncSession, execution_id: int, user_id: int
    ) -> ExecutionResponse:
        """Fetch an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.
            user_id: The owner user ID.

        Returns:
            The execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if not execution:
            raise ExecutionNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=execution.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return ExecutionResponse.model_validate(execution)

    async def cancel_execution(
        self,
        session: AsyncSession,
        execution_id: int,
        user_id: int,
    ) -> ExecutionResponse:
        """Cancel a queued or running execution.

        Args:
            session: The session.
            execution_id: The execution ID.
            user_id: The owner user ID.

        Returns:
            The cancelled execution. Repeated cancellation is idempotent.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not owned by the user.
            ExecutionNotCancellableError: If the execution already finished.

        """
        current = await self.get_execution(
            session=session, execution_id=execution_id, user_id=user_id
        )
        if current.status is ExecutionStatus.CANCELLED:
            return current
        if current.status not in {
            ExecutionStatus.CREATED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.WAITING_APPROVAL,
            ExecutionStatus.WAITING_DELAY,
        }:
            raise ExecutionNotCancellableError

        (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = await self._node_execution_repository.sum_tokens(
            session=session, execution_id=execution_id
        )
        won = await self._execution_repository.update_status_if(
            session=session,
            execution_id=execution_id,
            expected_status=current.status,
            data={
                "status": ExecutionStatus.CANCELLED,
                "error": None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "finished_at": datetime.now(tz=UTC),
                "approval_node_id": None,
                "approval_prompt": None,
                "approval_input": None,
                "wait_until": None,
            },
        )
        if not won:
            latest = await self.get_execution(
                session=session, execution_id=execution_id, user_id=user_id
            )
            if latest.status is ExecutionStatus.CANCELLED:
                return latest
            raise ExecutionNotCancellableError

        try:
            if (
                current.status is ExecutionStatus.WAITING_APPROVAL
                and current.approval_node_id is not None
            ):
                await self._node_execution_repository.update_by(
                    session=session,
                    execution_id=execution_id,
                    node_id=current.approval_node_id,
                    status=ExecutionStatus.WAITING_APPROVAL,
                    data={
                        "status": ExecutionStatus.CANCELLED,
                        "error": None,
                        "finished_at": datetime.now(tz=UTC),
                    },
                )
            if current.status is ExecutionStatus.WAITING_DELAY:
                waiting_delays = await self._node_execution_repository.get_all(
                    session=session,
                    execution_id=execution_id,
                    status=ExecutionStatus.WAITING_DELAY,
                )
                for waiting_delay in waiting_delays:
                    await self._node_execution_repository.update_by(
                        session=session,
                        id=waiting_delay.id,
                        data={
                            "status": ExecutionStatus.CANCELLED,
                            "error": None,
                            "finished_at": datetime.now(tz=UTC),
                        },
                    )
            await self._usage_usecase.record_run(
                session=session,
                user_id=user_id,
                total_tokens=total_tokens,
            )
            await self._audit_usecase.record(
                session=session,
                event=AuditEvent(
                    user_id=user_id,
                    action="execution.cancel",
                    entity_type="execution",
                    entity_id=execution_id,
                    metadata={"previous_status": current.status.value},
                ),
            )
            await session.commit()
        except Exception:
            logger.exception(
                "Failed to record cancellation usage for execution %s",
                execution_id,
            )
            await session.rollback()

        return await self.get_execution(
            session=session, execution_id=execution_id, user_id=user_id
        )

    async def approve_execution(
        self,
        session: AsyncSession,
        execution_id: int,
        user_id: int,
    ) -> ExecutionResponse:
        """Approve the current checkpoint and make the execution queueable."""
        return await self._decide_execution_approval(
            session=session,
            execution_id=execution_id,
            user_id=user_id,
            approved=True,
        )

    async def reject_execution(
        self,
        session: AsyncSession,
        execution_id: int,
        user_id: int,
    ) -> ExecutionResponse:
        """Reject the current checkpoint and finalize the execution."""
        return await self._decide_execution_approval(
            session=session,
            execution_id=execution_id,
            user_id=user_id,
            approved=False,
        )

    async def _decide_execution_approval(
        self,
        session: AsyncSession,
        execution_id: int,
        user_id: int,
        *,
        approved: bool,
    ) -> ExecutionResponse:
        """Apply one owner decision to a locked approval checkpoint."""
        execution = await self._execution_repository.get_by_id_for_update(
            session=session, execution_id=execution_id
        )
        if execution is None:
            raise ExecutionNotFoundError
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=execution.workflow_id,
            owner_id=user_id,
        )
        if workflow is None:
            raise WorkflowNotFoundError
        if (
            execution.status is not ExecutionStatus.WAITING_APPROVAL
            or execution.approval_node_id is None
        ):
            raise ExecutionApprovalNotPendingError

        node_id = execution.approval_node_id
        approval_input = execution.approval_input or ""
        node_execution = await self._node_execution_repository.update_by(
            session=session,
            execution_id=execution_id,
            node_id=node_id,
            status=ExecutionStatus.WAITING_APPROVAL,
            data={
                "status": (
                    ExecutionStatus.SUCCESS if approved else ExecutionStatus.REJECTED
                ),
                "output": approval_input if approved else None,
                "error": None if approved else "Rejected by workflow owner",
                "finished_at": datetime.now(tz=UTC),
            },
        )
        if node_execution is None:
            raise ExecutionApprovalNotPendingError

        action = "approve" if approved else "reject"
        execution_data: dict[str, object] = {
            "status": (
                ExecutionStatus.CREATED if approved else ExecutionStatus.REJECTED
            ),
            "error": None,
        }
        if approved:
            execution_data.update(
                {
                    "approval_node_id": None,
                    "approval_prompt": None,
                    "approval_input": None,
                    "finished_at": None,
                    "queue_job_id": (f"execution:{execution_id}:resume:{uuid4().hex}"),
                }
            )
        else:
            (
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ) = await self._node_execution_repository.sum_tokens(
                session=session, execution_id=execution_id
            )
            execution_data.update(
                {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "finished_at": datetime.now(tz=UTC),
                }
            )
            await self._usage_usecase.record_run(
                session=session,
                user_id=user_id,
                total_tokens=total_tokens,
            )

        await self._execution_repository.update_by(
            session=session,
            id=execution_id,
            data=execution_data,
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action=f"execution.{action}",
                entity_type="execution",
                entity_id=execution_id,
                metadata={"node_id": node_id},
            ),
        )
        await session.commit()

        return await self.get_execution(
            session=session,
            execution_id=execution_id,
            user_id=user_id,
        )

    async def get_node_executions(
        self,
        session: AsyncSession,
        execution_id: int,
        user_id: int,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> list[NodeExecutionResponse]:
        """List per-node results for an execution.

        Args:
            session: The session.
            execution_id: The execution ID.
            user_id: The owner user ID.
            limit: Maximum node results to return.
            offset: Node results to skip (for paging).

        Returns:
            The list of node execution results.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not owned by the user.

        """
        await self.get_execution(
            session=session, execution_id=execution_id, user_id=user_id
        )

        return [
            NodeExecutionResponse.model_validate(node_execution)
            for node_execution in await self._node_execution_repository.get_all(
                session=session,
                limit=limit,
                offset=offset,
                execution_id=execution_id,
            )
        ]

    async def stream_execution(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        execution_id: int,
        user_id: int,
        pool: Redis,
    ) -> AsyncGenerator[str, None]:
        """Stream an execution's status and live LLM tokens as SSE frames.

        Two producers feed one queue: a Redis pub/sub listener for per-node token
        deltas, and a database poller for status snapshots. The generator drains
        the queue until the execution reaches a terminal status.

        Args:
            session_factory: Factory for a short-lived session per status poll,
                rather than pinning one pooled connection for the whole stream
                (which can run for minutes).
            execution_id: The execution ID.
            user_id: The owner user ID.
            pool: Redis connection for the token pub/sub channel.

        Yields:
            SSE ``data:`` frames of ``status`` snapshots and ``token`` deltas.

        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        token_task = asyncio.create_task(
            self._pump_tokens(queue=queue, pool=pool, execution_id=execution_id)
        )
        status_task = asyncio.create_task(
            self._pump_status(
                queue=queue,
                session_factory=session_factory,
                execution_id=execution_id,
                user_id=user_id,
            )
        )
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
            while not queue.empty():
                remaining = queue.get_nowait()
                if remaining is not None:
                    yield remaining
        finally:
            token_task.cancel()
            status_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await token_task
            with contextlib.suppress(asyncio.CancelledError):
                await status_task

    @staticmethod
    async def _pump_tokens(
        queue: asyncio.Queue[str | None],
        pool: Redis,
        execution_id: int,
    ) -> None:
        """Forward published token deltas onto the queue (best-effort).

        Args:
            queue: Destination queue for SSE frames.
            pool: Redis connection for the token pub/sub channel.
            execution_id: The execution ID.

        """
        try:
            async for node_id, delta, reset in subscribe_tokens(pool, execution_id):
                if reset:
                    frame = json.dumps({"type": "token_reset", "node_id": node_id})
                else:
                    frame = json.dumps(
                        {"type": "token", "node_id": node_id, "delta": delta}
                    )
                await queue.put(f"data: {frame}\n\n")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Token streaming is best-effort; a pub/sub failure must not break the
            # status stream, which is the source of truth for completion.
            logger.exception("Token stream failed for execution %s", execution_id)

    async def _pump_status(
        self,
        queue: asyncio.Queue[str | None],
        session_factory: async_sessionmaker[AsyncSession],
        execution_id: int,
        user_id: int,
    ) -> None:
        """Poll status snapshots onto the queue until terminal.

        Args:
            queue: Destination queue for SSE frames.
            session_factory: Factory for a short-lived session per poll, so a
                slow/long-running stream doesn't pin one pooled connection for
                its whole duration.
            execution_id: The execution ID.
            user_id: The owner user ID.

        """
        terminal = {
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
        }
        reached_terminal = False
        for _ in range(STREAM_MAX_ITERATIONS):
            async with session_factory() as session:
                execution = await self.get_execution(
                    session=session, execution_id=execution_id, user_id=user_id
                )
            frame = json.dumps(
                {"type": "status", "execution": execution.model_dump(mode="json")}
            )
            await queue.put(f"data: {frame}\n\n")
            if execution.status in terminal:
                reached_terminal = True
                break
            await asyncio.sleep(STREAM_POLL_SECONDS)

        if not reached_terminal:
            # Cap hit while still running: tell the client to resume polling
            # instead of silently closing (which reads as "done").
            await queue.put(f"data: {json.dumps({'type': 'expired'})}\n\n")
        await queue.put(None)

    async def _run_execution(
        self,
        session: AsyncSession,
        execution_id: int,
        loaded_graph: _LoadedGraph,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        token_publishers: _TokenPublishers | None = None,
    ) -> ExecutionOutputPayload:
        """Execute workflow nodes for an execution and return output payload.

        Args:
            session: Database session.
            execution_id: Execution ID.
            loaded_graph: Validated top-level graph, bundled with the
                workflow's full (every-scope) node/edge list — the latter is
                threaded into `_NodeRunContext` so a Loop node encountered
                mid-run can build its own body's `ExecutionGraphContext`
                on demand.
            session_factory: When provided, independent branches run concurrently.
            token_publishers: Callbacks for streaming token deltas and, before
                a retry, signaling clients to discard a node's already-streamed
                text.

        Returns:
            Output payload.

        Raises:
            ExecutionNotFoundError: If execution is not found.
            WorkflowNotFoundError: If workflow is not found.
            ExecutionGraphValidationError: If graph is invalid.
            ExecutionInputValidationError: If input payload is invalid.

        """
        token_publishers = token_publishers or _TokenPublishers()
        execution = await self._execution_repository.get_by(
            session=session,
            id=execution_id,
        )
        if execution is None:
            raise ExecutionNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session,
            id=execution.workflow_id,
        )
        if workflow is None:
            raise WorkflowNotFoundError

        graph = loaded_graph.top_level
        run_context = _NodeRunContext(
            execution_id=execution_id,
            workflow_id=workflow.id,
            workflow_owner_id=workflow.owner_id,
            input_value=self._extract_input_value(input_data=execution.input_data),
            graph_source=loaded_graph.source,
            called_graphs=loaded_graph.called_graphs,
            workflow_call_stack=(workflow.id,),
            token_publisher=token_publishers.delta,
            token_reset_publisher=token_publishers.reset,
        )

        if session_factory is None:
            outputs_by_node = await self._run_nodes_serial(
                session=session, run_context=run_context, graph=graph
            )
        else:
            outputs_by_node = await self._run_nodes_parallel(
                session=session,
                run_context=run_context,
                graph=graph,
                session_factory=session_factory,
            )

        return ExecutionOutputPayload(
            value=outputs_by_node[graph.output_node_id].to_legacy_text()
        )

    def _resolve_live_parents(  # noqa: PLR0913 - scheduler state is map-based
        self,
        node_id: int,
        graph: ExecutionGraphContext,
        outputs_by_node: dict[int, NodeValue],
        named_outputs_by_node: dict[int, dict[str, NodeValue]],
        live_by_node: dict[int, bool],
        selected_handle_by_node: dict[int, str | None],
    ) -> tuple[list[NodeValue], dict[str, tuple[NodeValue, ...]], bool]:
        """Gather live parent outputs for a node and whether it should run.

        A parent edge is live when its source node itself ran (not skipped)
        and, for branching nodes (e.g. Condition), the edge's handle matches
        the branch the source node selected. A node with zero live inbound
        edges is skipped rather than executed.

        Args:
            node_id: Node whose inputs are being resolved.
            graph: Validated graph context.
            outputs_by_node: Outputs recorded so far.
            named_outputs_by_node: Additional ordinary outputs by source node.
            live_by_node: Whether each already-resolved node ran (vs skipped).
            selected_handle_by_node: Branch handle selected by each node, if any.

        Returns:
            The live parent outputs, values grouped by target handle, and whether
            the node has at least one live inbound edge.

        """
        live_outputs: list[NodeValue] = []
        grouped: dict[str, list[NodeValue]] = {}
        target_ports = get_node_definition(graph.nodes_by_id[node_id].type).graph.inputs
        primary_input_name = target_ports[0].name if target_ports else "input"
        for parent_id, source_handle, target_handle, coercion in graph.inbound_edges[
            node_id
        ]:
            if not live_by_node.get(parent_id, False):
                continue
            parent = graph.nodes_by_id[parent_id]
            routing_handles = get_node_output_handles(parent.type, parent.data)
            if (
                routing_handles is not None
                and source_handle != selected_handle_by_node.get(parent_id)
            ):
                continue
            if source_handle is None or routing_handles is not None:
                source_value = outputs_by_node[parent_id]
            else:
                source_value = named_outputs_by_node.get(parent_id, {}).get(
                    source_handle
                )
                if source_value is None:
                    raise ExecutionGraphValidationError(
                        message=(
                            f"Node {parent_id} did not produce output handle "
                            f"'{source_handle}'"
                        )
                    )
            value = coerce_node_value(source_value, coercion)
            live_outputs.append(value)
            input_name = target_handle or primary_input_name
            grouped.setdefault(input_name, []).append(value)
        return (
            live_outputs,
            {name: tuple(values) for name, values in grouped.items()},
            bool(live_outputs),
        )

    async def _record_skip(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        iteration: int | None = None,
    ) -> None:
        """Persist a SKIPPED result for a node with no live inbound edge.

        Args:
            session: Database session to record the result on.
            run_context: Loop-invariant run context.
            node: The skipped node.
            iteration: The loop iteration this node belongs to, if any — see
                `_run_loop_node`. `None` for a top-level node.

        """
        await self._record_node_result(
            session=session,
            run_context=run_context,
            node=node,
            started_at=datetime.now(tz=UTC),
            outcome=_NodeOutcome(status=ExecutionStatus.SKIPPED, iteration=iteration),
        )

    async def _record_skip_isolated(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        run_context: _NodeRunContext,
        node: NodeResponse,
    ) -> None:
        """Persist a SKIPPED result for a node on a dedicated session.

        Args:
            session_factory: Factory for the node's own session.
            run_context: Loop-invariant run context.
            node: The skipped node.

        """
        async with session_factory() as skip_session:
            await self._record_skip(
                session=skip_session, run_context=run_context, node=node
            )

    def _raise_if_output_not_live(
        self, graph: ExecutionGraphContext, live_by_node: dict[int, bool]
    ) -> None:
        """Fail the run when no live branch ever reached the output node.

        Args:
            graph: Validated graph context.
            live_by_node: Whether each node ran (vs was skipped).

        Raises:
            ExecutionGraphValidationError: If the output node was skipped.

        """
        if not live_by_node.get(graph.output_node_id, False):
            message = "No live path reached the output node"
            raise ExecutionGraphValidationError(message=message)

    async def _load_resolved_node_executions(
        self,
        session: AsyncSession,
        execution_id: int,
        graph: ExecutionGraphContext,
        iteration: int | None,
    ) -> dict[int, "NodeExecution"]:
        """Load successful/skipped checkpoints for one graph scope."""
        rows = await self._node_execution_repository.get_all(
            session=session,
            execution_id=execution_id,
            iteration=iteration,
            status=[ExecutionStatus.SUCCESS, ExecutionStatus.SKIPPED],
        )
        return {row.node_id: row for row in rows if row.node_id in graph.nodes_by_id}

    def _restore_node_result(
        self,
        node: NodeResponse,
        node_execution: "NodeExecution",
    ) -> NodeExecutionResult:
        """Rebuild an in-memory result from a durable successful checkpoint."""
        output_values: dict[str, NodeValue] = {}
        if node_execution.output_values is not None:
            try:
                output_values = {
                    name: NodeValue.from_payload(payload)
                    for name, payload in node_execution.output_values.items()
                }
            except (TypeError, ValueError) as exc:
                raise ExecutionGraphValidationError(
                    message="Stored node output handle envelopes are invalid"
                ) from exc
        primary_ports = get_node_definition(node.type).graph.outputs
        primary_name = primary_ports[0].name if primary_ports else "output"
        if node_execution.output_value is not None:
            try:
                output_value = NodeValue.from_payload(node_execution.output_value)
            except (TypeError, ValueError) as exc:
                raise ExecutionGraphValidationError(
                    message="Stored node output envelope is invalid"
                ) from exc
        elif primary_name in output_values:
            output_value = output_values[primary_name]
        else:
            output_value = NodeValue.text(node_execution.output or "")
        additional_outputs = {
            name: value for name, value in output_values.items() if name != primary_name
        }
        selected_handle: str | None = None
        if node.type is NodeType.CONDITION:
            output = output_value.require_text()
            try:
                condition_type = ConditionType(node.data.get("condition_type"))
            except ValueError as exc:
                raise ExecutionGraphValidationError(
                    message="Condition node has an unsupported condition_type"
                ) from exc
            raw_value = node.data.get("value")
            matched = evaluate_condition(
                condition_type=condition_type,
                text=output,
                case_sensitive=node.data.get("case_sensitive") == "true",
                value=raw_value if isinstance(raw_value, str) else None,
            )
            selected_handle = "true" if matched else "false"
        elif node.type is NodeType.SWITCH:
            output = output_value.require_text()
            try:
                selected_handle = select_switch_handle(node.data, output)
            except ValueError as exc:
                raise ExecutionGraphValidationError(message=str(exc)) from exc
        return NodeExecutionResult(
            output=output_value,
            selected_handle=selected_handle,
            outputs=additional_outputs,
        )

    async def _run_nodes_serial(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        graph: ExecutionGraphContext,
        iteration: int | None = None,
    ) -> dict[int, NodeValue]:
        """Run nodes one at a time in topological order.

        Args:
            session: Database session shared by all nodes.
            run_context: Loop-invariant run context.
            graph: Validated graph context.
            iteration: When running a Loop node's body (see
                `_run_loop_node`), the 0-based index of this pass, recorded
                on every inner node's `node_executions` row so a rerun of
                the same node across iterations is distinguishable. `None`
                for the top-level graph.

        Returns:
            Mapping of node ID to output text.

        """
        outputs_by_node: dict[int, NodeValue] = {}
        named_outputs_by_node: dict[int, dict[str, NodeValue]] = {}
        live_by_node: dict[int, bool] = {}
        selected_handle_by_node: dict[int, str | None] = {}
        resolved = await self._load_resolved_node_executions(
            session=session,
            execution_id=run_context.execution_id,
            graph=graph,
            iteration=iteration,
        )

        for index, node_id in enumerate(graph.topological_order):
            node = graph.nodes_by_id[node_id]
            existing = resolved.get(node_id)
            if existing is not None:
                if existing.status is ExecutionStatus.SKIPPED:
                    live_by_node[node_id] = False
                    selected_handle_by_node[node_id] = None
                else:
                    restored = self._restore_node_result(
                        node=node, node_execution=existing
                    )
                    outputs_by_node[node_id] = restored.output
                    named_outputs_by_node[node_id] = restored.outputs
                    live_by_node[node_id] = True
                    selected_handle_by_node[node_id] = restored.selected_handle
                continue

            if node_id == graph.input_node_id:
                parent_values: list[NodeValue] = []
                values_by_input: dict[str, tuple[NodeValue, ...]] = {}
                is_live = True
            else:
                parent_values, values_by_input, is_live = self._resolve_live_parents(
                    node_id=node_id,
                    graph=graph,
                    outputs_by_node=outputs_by_node,
                    named_outputs_by_node=named_outputs_by_node,
                    live_by_node=live_by_node,
                    selected_handle_by_node=selected_handle_by_node,
                )

            if not is_live:
                live_by_node[node_id] = False
                selected_handle_by_node[node_id] = None
                await self._record_skip(
                    session=session,
                    run_context=run_context,
                    node=node,
                    iteration=iteration,
                )
                continue

            try:
                result = await self._run_node(
                    session=session,
                    run_context=run_context,
                    node=node,
                    parent_values=parent_values,
                    values_by_input=values_by_input,
                    iteration=iteration,
                )
            except BaseError:
                # This node's own failure is already recorded; nodes later in
                # topological order that the abort never reaches get a
                # SKIPPED row instead of no row at all.
                for unreached_id in graph.topological_order[index + 1 :]:
                    await self._record_skip(
                        session=session,
                        run_context=run_context,
                        node=graph.nodes_by_id[unreached_id],
                        iteration=iteration,
                    )
                raise
            outputs_by_node[node_id] = result.output
            named_outputs_by_node[node_id] = result.outputs
            live_by_node[node_id] = True
            selected_handle_by_node[node_id] = result.selected_handle

        self._raise_if_output_not_live(graph=graph, live_by_node=live_by_node)
        return outputs_by_node

    async def _prepare_wave(
        self,
        ready: list[int],
        graph: ExecutionGraphContext,
        state: _WaveState,
        run_context: _NodeRunContext,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> tuple[
        list[int],
        dict[int, list[NodeValue]],
        dict[int, dict[str, tuple[NodeValue, ...]]],
    ]:
        """Split a wave's ready nodes into runnable ones vs. dead-branch skips.

        Args:
            ready: Node IDs whose parents have all resolved.
            graph: Validated graph context.
            state: Per-node bookkeeping so far; mutated in place for newly-
                skipped nodes.
            run_context: Loop-invariant run context.
            session_factory: Factory for per-node sessions.

        Returns:
            The runnable node IDs and each one's live parent outputs.

        """
        runnable: list[int] = []
        parent_values_by_node: dict[int, list[NodeValue]] = {}
        values_by_input_by_node: dict[int, dict[str, tuple[NodeValue, ...]]] = {}
        for node_id in ready:
            existing = state.resolved_by_node.get(node_id)
            if existing is not None:
                if existing.status is ExecutionStatus.SKIPPED:
                    state.live_by_node[node_id] = False
                    state.selected_handle_by_node[node_id] = None
                else:
                    restored = self._restore_node_result(
                        node=graph.nodes_by_id[node_id],
                        node_execution=existing,
                    )
                    state.outputs_by_node[node_id] = restored.output
                    state.named_outputs_by_node[node_id] = restored.outputs
                    state.live_by_node[node_id] = True
                    state.selected_handle_by_node[node_id] = restored.selected_handle
                continue

            if node_id == graph.input_node_id:
                parent_values_by_node[node_id] = []
                values_by_input_by_node[node_id] = {}
                runnable.append(node_id)
                continue

            parent_values, values_by_input, is_live = self._resolve_live_parents(
                node_id=node_id,
                graph=graph,
                outputs_by_node=state.outputs_by_node,
                named_outputs_by_node=state.named_outputs_by_node,
                live_by_node=state.live_by_node,
                selected_handle_by_node=state.selected_handle_by_node,
            )
            if is_live:
                parent_values_by_node[node_id] = parent_values
                values_by_input_by_node[node_id] = values_by_input
                runnable.append(node_id)
            else:
                state.live_by_node[node_id] = False
                state.selected_handle_by_node[node_id] = None
                await self._record_skip_isolated(
                    session_factory=session_factory,
                    run_context=run_context,
                    node=graph.nodes_by_id[node_id],
                )

        return runnable, parent_values_by_node, values_by_input_by_node

    async def _run_nodes_parallel(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        graph: ExecutionGraphContext,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> dict[int, NodeValue]:
        """Run nodes wave by wave, concurrently within each wave.

        Each node runs on its own session so concurrent nodes never share one
        AsyncSession. A node becomes ready once all its parents have completed.

        Args:
            session: Worker session used to load durable checkpoints.
            run_context: Loop-invariant run context.
            graph: Validated graph context.
            session_factory: Factory for per-node sessions.

        Returns:
            Mapping of node ID to typed output value.

        Raises:
            BaseError: If any node fails after exhausting its attempts.

        """
        indegree = {
            node_id: len(graph.inbound[node_id]) for node_id in graph.nodes_by_id
        }
        resolved = await self._load_resolved_node_executions(
            session=session,
            execution_id=run_context.execution_id,
            graph=graph,
            iteration=None,
        )
        state = _WaveState(
            outputs_by_node={},
            named_outputs_by_node={},
            live_by_node={},
            selected_handle_by_node={},
            resolved_by_node=resolved,
        )
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]

        while ready:
            (
                runnable,
                parent_values_by_node,
                values_by_input_by_node,
            ) = await self._prepare_wave(
                ready=ready,
                graph=graph,
                state=state,
                run_context=run_context,
                session_factory=session_factory,
            )

            wave_results = await asyncio.gather(
                *(
                    self._run_node_isolated(
                        session_factory=session_factory,
                        run_context=run_context,
                        node=graph.nodes_by_id[node_id],
                        parent_values=parent_values_by_node[node_id],
                        values_by_input=values_by_input_by_node[node_id],
                    )
                    for node_id in runnable
                ),
                return_exceptions=True,
            )
            failures: list[BaseException] = []
            for result in wave_results:
                if isinstance(result, BaseException):
                    failures.append(result)
                    continue
                node_id, node_result = result
                state.outputs_by_node[node_id] = node_result.output
                state.named_outputs_by_node[node_id] = node_result.outputs
                state.live_by_node[node_id] = True
                state.selected_handle_by_node[node_id] = node_result.selected_handle

            paused = next(
                (
                    failure
                    for failure in failures
                    if isinstance(failure, _ExecutionPausedError)
                ),
                None,
            )
            if paused is not None:
                raise paused

            if failures:
                reached = (
                    set(state.outputs_by_node) | set(state.live_by_node) | set(runnable)
                )
                await self._handle_wave_failures(
                    failures=failures,
                    reached=reached,
                    graph=graph,
                    run_context=run_context,
                    session_factory=session_factory,
                )

            next_ready: list[int] = []
            for node_id in ready:
                for child_id in graph.outbound[node_id]:
                    indegree[child_id] -= 1
                    if indegree[child_id] == 0:
                        next_ready.append(child_id)
            ready = next_ready

        self._raise_if_output_not_live(graph=graph, live_by_node=state.live_by_node)
        return state.outputs_by_node

    async def _handle_wave_failures(
        self,
        failures: list[BaseException],
        reached: set[int],
        graph: ExecutionGraphContext,
        run_context: _NodeRunContext,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Record unreached nodes as SKIPPED, then raise an aggregated error.

        Each failed node already recorded its own FAILED row (via
        ``_run_node``'s retry loop); nodes in waves that were never reached
        because this wave aborted the run get a SKIPPED row instead of no
        row at all, so the UI can tell "failed" from "never ran".

        Args:
            failures: The exceptions raised by this wave's failed nodes.
            reached: Node IDs already resolved (success or failure) this wave.
            graph: Validated graph context.
            run_context: Loop-invariant run context.
            session_factory: Factory for per-node sessions.

        Raises:
            BaseException: The aggregated failure for this wave.

        """
        for node_id in set(graph.nodes_by_id) - reached:
            await self._record_skip_isolated(
                session_factory=session_factory,
                run_context=run_context,
                node=graph.nodes_by_id[node_id],
            )
        raise self._aggregate_wave_errors(failures)

    @staticmethod
    def _aggregate_wave_errors(failures: list[BaseException]) -> BaseException:
        """Combine simultaneous node failures from one wave into one error.

        Each failing node already recorded its own error in
        ``node_executions``; this only decides what the *overall execution's*
        failure reason says, so a wave where several nodes fail at once
        doesn't just report one of them arbitrarily.

        Args:
            failures: The exceptions raised by this wave's failed nodes.

        Returns:
            One exception summarizing all of them.

        """
        base_errors = [
            failure for failure in failures if isinstance(failure, BaseError)
        ]
        if len(base_errors) != len(failures):
            # A non-domain exception (an actual bug) shouldn't be swallowed
            # into a domain-error message; let it surface as-is.
            return next(f for f in failures if not isinstance(f, BaseError))
        if len(base_errors) == 1:
            return base_errors[0]

        combined = "; ".join(error.message for error in base_errors)
        message = f"{len(base_errors)} nodes failed: {combined}"
        return type(base_errors[0])(message=message)

    async def _run_node_isolated(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
        values_by_input: dict[str, tuple[NodeValue, ...]],
    ) -> tuple[int, NodeExecutionResult]:
        """Run one node on a dedicated session and return its ID and result.

        Args:
            session_factory: Factory for the node's own session.
            run_context: Loop-invariant run context.
            node: Node to execute.
            parent_values: Outputs of the node's parents.
            values_by_input: Parent values grouped by declared target handle.

        Returns:
            The node ID paired with its execution result.

        """
        async with session_factory() as node_session:
            result = await self._run_node(
                session=node_session,
                run_context=run_context,
                node=node,
                parent_values=parent_values,
                values_by_input=values_by_input,
            )

        return node.id, result

    async def _run_node(  # noqa: PLR0913 - execution and resolved-input contexts
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
        values_by_input: dict[str, tuple[NodeValue, ...]],
        iteration: int | None = None,
    ) -> NodeExecutionResult:
        """Run one node with retries, persisting its final result.

        Args:
            session: Database session.
            run_context: Loop-invariant run context.
            node: Node to execute.
            parent_values: Outputs of the node's parents.
            values_by_input: Parent values grouped by declared target handle.
            iteration: The loop iteration this node belongs to, if any — see
                `_run_nodes_serial`. `None` for a top-level node.

        Returns:
            The node execution result.

        Raises:
            BaseError: If the node fails after exhausting its attempts.

        """
        started_at = datetime.now(tz=UTC)
        for attempt in range(1, self._max_node_attempts + 1):
            try:
                result = await self._run_node_once(
                    session=session,
                    run_context=run_context,
                    node=node,
                    parent_values=parent_values,
                    values_by_input=values_by_input,
                )
                self._validate_node_result(node=node, result=result)
            except BaseError as exc:
                if exc.retryable and attempt < self._max_node_attempts:
                    logger.warning(
                        "Node %s attempt %s failed (retryable): %s; retrying",
                        node.id,
                        attempt,
                        exc.message,
                    )
                    if run_context.token_reset_publisher is not None:
                        # The failed attempt may have already streamed partial
                        # tokens; tell clients to discard them before the
                        # retry starts streaming from scratch.
                        await run_context.token_reset_publisher(
                            run_context.execution_id, node.id
                        )
                    await asyncio.sleep(self._retry_delay(attempt=attempt))
                    continue

                await self._record_node_result(
                    session=session,
                    run_context=run_context,
                    node=node,
                    started_at=started_at,
                    outcome=_NodeOutcome(
                        status=ExecutionStatus.FAILED,
                        error=exc.message,
                        iteration=iteration,
                    ),
                )
                raise

            await self._record_node_result(
                session=session,
                run_context=run_context,
                node=node,
                started_at=started_at,
                outcome=_NodeOutcome(
                    status=ExecutionStatus.SUCCESS,
                    output=result.output,
                    outputs=result.outputs,
                    iteration=iteration,
                    usage=result.usage,
                ),
            )
            return result

        # Unreachable: the loop always returns or raises, but satisfies typing.
        message = f"Node {node.id} exhausted retries"
        raise ExecutionGraphValidationError(message=message)

    def _validate_node_result(
        self,
        node: NodeResponse,
        result: NodeExecutionResult,
    ) -> None:
        """Require handler outputs to match the node's declared ordinary ports."""
        graph = get_node_definition(node.type).graph
        if not graph.outputs:
            return
        primary_type = get_node_output_port(node.type, node.data)
        if primary_type is not None and result.output.kind is not primary_type:
            raise ExecutionGraphValidationError(
                message=(
                    f"Node {node.id} produced '{result.output.kind.value}' on its "
                    f"primary output; expected '{primary_type.value}'"
                )
            )
        if graph.output_handles is not None:
            if result.outputs:
                raise ExecutionGraphValidationError(
                    message=f"Routing node {node.id} produced ordinary named outputs"
                )
            return
        declared = {port.name: port for port in graph.outputs[1:]}
        unknown = sorted(set(result.outputs) - set(declared))
        if unknown:
            raise ExecutionGraphValidationError(
                message=(
                    f"Node {node.id} produced undeclared output handle(s): "
                    f"{', '.join(unknown)}"
                )
            )
        missing = sorted(
            name
            for name, port in declared.items()
            if port.required and name not in result.outputs
        )
        if missing:
            raise ExecutionGraphValidationError(
                message=(
                    f"Node {node.id} did not produce required output handle(s): "
                    f"{', '.join(missing)}"
                )
            )
        for name, value in result.outputs.items():
            expected = get_node_output_port(node.type, node.data, name)
            if expected is not None and value.kind is not expected:
                raise ExecutionGraphValidationError(
                    message=(
                        f"Node {node.id} produced '{value.kind.value}' on output "
                        f"'{name}'; expected '{expected.value}'"
                    )
                )

    async def _run_node_once(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
        values_by_input: dict[str, tuple[NodeValue, ...]],
    ) -> NodeExecutionResult:
        """Execute a single node attempt within its time budget.

        Args:
            session: Database session.
            run_context: Loop-invariant run context.
            node: Node to execute.
            parent_values: Outputs of the node's parents.
            values_by_input: Parent values grouped by declared target handle.

        Returns:
            The node execution result.

        Raises:
            ExecutionGraphValidationError: If a non-input node has no input.
            NodeExecutionTimeoutError: If the node exceeds its time budget.
            BaseError: If the node handler fails.

        """
        if node.type not in {NodeType.INPUT, NodeType.LOOP_INPUT} and not parent_values:
            message = f"Node {node.id} does not have input value"
            raise ExecutionGraphValidationError(message=message)

        # Loop can't be a plain NodeHandler like every other type — running
        # its body means recursively calling back into the graph runner
        # itself, which a handler (only ever given one NodeExecutionContext)
        # has no way to do. Special-cased here, before the node registry
        # dispatch below, and deliberately outside the per-node timeout: a
        # Loop's total runtime is bounded by (iterations x each inner
        # node's own timeout) instead, not one fixed budget — see
        # `_run_loop_node`. See also `nodes/loop.py`'s module docstring.
        if node.type is NodeType.LOOP:
            return await self._run_loop_node(
                session=session,
                run_context=run_context,
                node=node,
                parent_values=parent_values,
            )

        if node.type is NodeType.CALL_WORKFLOW:
            return await self._run_call_workflow_node(
                session=session,
                run_context=run_context,
                node=node,
                parent_values=parent_values,
            )

        if node.type is NodeType.DELAY:
            return await self._pause_for_delay(
                session=session,
                run_context=run_context,
                node=node,
                parent_values=parent_values,
            )

        if node.type is NodeType.APPROVAL:
            await self._pause_for_approval(
                session=session,
                run_context=run_context,
                node=node,
                parent_values=parent_values,
            )

        try:
            async with asyncio.timeout(self._node_timeout_seconds):
                return await self._node_registry.execute(
                    node_type=node.type,
                    context=NodeExecutionContext(
                        session=session,
                        workflow_owner_id=run_context.workflow_owner_id,
                        node_data=node.data,
                        parent_values=parent_values,
                        input_value=run_context.input_value,
                        values_by_input=values_by_input,
                        primary_input_name=(
                            get_node_definition(node.type).graph.inputs[0].name
                            if get_node_definition(node.type).graph.inputs
                            else "input"
                        ),
                        on_token=self._make_on_token(
                            run_context=run_context, node_id=node.id
                        ),
                    ),
                )
        except TimeoutError as exc:
            raise NodeExecutionTimeoutError from exc

    async def _pause_for_delay(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
    ) -> NodeExecutionResult:
        """Persist a durable Delay checkpoint and release the worker."""
        now = datetime.now(tz=UTC)
        output = _join_text_values(parent_values)
        existing = await self._node_execution_repository.get_by(
            session=session,
            execution_id=run_context.execution_id,
            node_id=node.id,
            status=ExecutionStatus.WAITING_DELAY,
        )
        if existing is not None and existing.wait_until is not None:
            wait_until = existing.wait_until
        else:
            wait_until = resolve_wait_until(node_data=node.data, now=now)

        if wait_until <= now:
            return NodeExecutionResult.text(output)

        execution = await self._execution_repository.get_by_id_for_update(
            session=session,
            execution_id=run_context.execution_id,
        )
        if execution is None:
            raise ExecutionNotFoundError
        if execution.status not in {
            ExecutionStatus.RUNNING,
            ExecutionStatus.WAITING_DELAY,
        }:
            await session.rollback()
            raise _ExecutionPausedError

        if existing is None:
            await self._node_execution_repository.create(
                session=session,
                data={
                    "execution_id": run_context.execution_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "node_label": node.data.get("label"),
                    "iteration": None,
                    "status": ExecutionStatus.WAITING_DELAY,
                    "output": _truncate_for_storage(output),
                    "error": None,
                    "started_at": now,
                    "finished_at": None,
                    "wait_until": wait_until,
                },
            )

        earliest_wait = wait_until
        if execution.wait_until is not None:
            earliest_wait = min(earliest_wait, execution.wait_until)
        execution_data: dict[str, object] = {
            "status": ExecutionStatus.WAITING_DELAY,
            "wait_until": earliest_wait,
            "heartbeat_at": now,
        }
        if execution.status is ExecutionStatus.RUNNING:
            execution_data["queue_job_id"] = (
                f"execution:{run_context.execution_id}:delay:{uuid4().hex}"
            )
        await self._execution_repository.update_by(
            session=session,
            id=run_context.execution_id,
            data=execution_data,
        )
        await session.commit()
        raise _ExecutionPausedError

    async def _pause_for_approval(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
    ) -> None:
        """Persist an approval checkpoint and stop the current worker attempt."""
        prompt = node.data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ExecutionGraphValidationError(
                message="Approval node requires a non-empty approval request"
            )

        execution = await self._execution_repository.get_by_id_for_update(
            session=session,
            execution_id=run_context.execution_id,
        )
        if execution is None:
            raise ExecutionNotFoundError
        if execution.status is not ExecutionStatus.RUNNING:
            await session.rollback()
            raise _ExecutionPausedError

        now = datetime.now(tz=UTC)
        approval_input = _join_text_values(parent_values)
        await self._node_execution_repository.create(
            session=session,
            data={
                "execution_id": run_context.execution_id,
                "node_id": node.id,
                "node_type": node.type,
                "node_label": node.data.get("label"),
                "iteration": None,
                "status": ExecutionStatus.WAITING_APPROVAL,
                "output": None,
                "error": None,
                "started_at": now,
                "finished_at": None,
            },
        )
        await self._execution_repository.update_by(
            session=session,
            id=run_context.execution_id,
            data={
                "status": ExecutionStatus.WAITING_APPROVAL,
                "approval_node_id": node.id,
                "approval_prompt": prompt.strip(),
                "approval_input": approval_input,
                "heartbeat_at": now,
            },
        )
        await session.commit()
        raise _ExecutionPausedError

    async def _run_call_workflow_node(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
    ) -> NodeExecutionResult:
        """Run another owned workflow inline and return its Output value.

        Args:
            session: The Call Workflow node's isolated/shared session.
            run_context: Context for the current workflow execution.
            node: Configured Call Workflow node.
            parent_values: Text values passed to the called workflow's Input.

        Returns:
            The called workflow's Output node value.

        Raises:
            ExecutionGraphValidationError: If the target is missing, foreign,
                recursive, too deeply nested, or has an invalid graph.

        """
        target_id = node.data.get("target_workflow_id")
        if not isinstance(target_id, int) or target_id <= 0:
            raise ExecutionGraphValidationError(
                message="Call Workflow node requires a target workflow"
            )
        if target_id in run_context.workflow_call_stack:
            chain = " -> ".join(
                str(item) for item in (*run_context.workflow_call_stack, target_id)
            )
            raise ExecutionGraphValidationError(
                message=f"Recursive workflow call detected: {chain}"
            )
        if len(run_context.workflow_call_stack) >= MAX_WORKFLOW_CALL_DEPTH:
            raise ExecutionGraphValidationError(
                message=(
                    "Call Workflow nesting exceeds the maximum depth of "
                    f"{MAX_WORKFLOW_CALL_DEPTH}"
                )
            )
        loaded = run_context.called_graphs.get(target_id)
        if loaded is None:
            # Backward-compatible fallback for legacy workflow versions that
            # predate embedded Call Workflow dependency snapshots.
            target = await self._workflow_repository.get_by(
                session=session,
                id=target_id,
                owner_id=run_context.workflow_owner_id,
            )
            if target is None:
                raise ExecutionGraphValidationError(
                    message="Referenced workflow does not exist"
                )
            loaded = await self._load_graph(session=session, workflow_id=target_id)
        nested_context = replace(
            run_context,
            workflow_id=target_id,
            input_value=NodeValue.text(_join_text_values(parent_values)),
            graph_source=loaded.source,
            called_graphs=loaded.called_graphs,
            workflow_call_stack=(*run_context.workflow_call_stack, target_id),
        )
        outputs = await self._run_nodes_serial(
            session=session,
            run_context=nested_context,
            graph=loaded.top_level,
        )
        return NodeExecutionResult(output=outputs[loaded.top_level.output_node_id])

    async def _run_loop_node(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        parent_values: list[NodeValue],
    ) -> NodeExecutionResult:
        """Run a Loop node's body to completion and return its aggregate result.

        Recursively drives the body's own scoped graph (`LOOP_INPUT` -> ...
        -> `LOOP_OUTPUT`) via `_run_nodes_serial`, entirely on `session`
        regardless of whether the outer execution is running serial or
        wave-parallel — loop iterations are inherently sequential (condition
        mode needs iteration N's result before iteration N+1 can start), so
        this never reuses the parallel wave machinery, even for independent
        branches within one iteration's body.

        Args:
            session: Database session (the Loop node's own — isolated
                per-node in wave-parallel mode, shared in serial mode;
                either way, every inner node this iterates over runs on it).
            run_context: Loop-invariant run context — carries the
                `_GraphSource` this builds the body's scope from.
            node: The Loop node itself.
            parent_values: The Loop node's own upstream input: list mode
                expects a JSON array as text; condition mode uses it as the
                seed value for the first iteration.

        Returns:
            List mode: a JSON array of each iteration's `LOOP_OUTPUT` text.
            Condition mode: the final iteration's `LOOP_OUTPUT` text.

        Raises:
            ExecutionGraphValidationError: If the body's graph is invalid,
                list mode's upstream text isn't a JSON array, or the mode/
                condition_type is unrecognized.
            BaseError: If an inner node fails after exhausting its own
                retries — same as any other node failure, this fails the
                Loop node's current attempt; the outer retry loop in
                `_run_node` then restarts the *whole* body from iteration 0
                (loop iterations aren't individually retried/resumed).

        """
        body_graph = self._build_scoped_graph_context(
            graph_source=run_context.graph_source, parent_node_id=node.id
        )
        seed_text = _join_text_values(parent_values)

        if node.data.get("mode") == LoopMode.CONDITION.value:
            return await self._run_loop_condition(
                session=session,
                run_context=run_context,
                node=node,
                body_graph=body_graph,
                seed_text=seed_text,
            )
        return await self._run_loop_list(
            session=session,
            run_context=run_context,
            node=node,
            body_graph=body_graph,
            seed_text=seed_text,
        )

    async def _run_loop_list(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        body_graph: ExecutionGraphContext,
        seed_text: str,
    ) -> NodeExecutionResult:
        """Run a Loop node's body once per element of a JSON array.

        Args:
            session: Database session for every inner node this runs.
            run_context: Loop-invariant run context.
            node: The Loop node itself.
            body_graph: The body's own validated `ExecutionGraphContext`.
            seed_text: The Loop node's upstream text, expected to parse as a
                JSON array.

        Returns:
            A JSON array of each element's `LOOP_OUTPUT` text, as the Loop
            node's own output — truncated (with a visible marker) past
            `MAX_LOOP_ITERATIONS` elements.

        Raises:
            ExecutionGraphValidationError: If `seed_text` isn't a JSON array.
            BaseError: If an inner node fails — see `_run_loop_node`.

        """
        try:
            items = json.loads(seed_text)
        except json.JSONDecodeError as exc:
            message = f"Loop node {node.id} (list mode) requires a JSON array as input"
            raise ExecutionGraphValidationError(message=message) from exc
        if not isinstance(items, list):
            message = f"Loop node {node.id} (list mode) requires a JSON array as input"
            raise ExecutionGraphValidationError(message=message)

        bounded_items = items[: self._max_loop_iterations]
        results: list[str] = []
        for index, item in enumerate(bounded_items):
            item_text = item if isinstance(item, str) else json.dumps(item)
            iteration_context = replace(
                run_context, input_value=NodeValue.text(item_text)
            )
            body_outputs = await self._run_nodes_serial(
                session=session,
                run_context=iteration_context,
                graph=body_graph,
                iteration=index,
            )
            results.append(body_outputs[body_graph.output_node_id].require_text())

        output = json.dumps(results)
        if len(items) > self._max_loop_iterations:
            output = (
                f"{output}\n\n[truncated: {len(items)} items total, "
                f"ran the first {self._max_loop_iterations}]"
            )
        return NodeExecutionResult.text(output)

    async def _run_loop_condition(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        body_graph: ExecutionGraphContext,
        seed_text: str,
    ) -> NodeExecutionResult:
        """Re-run a Loop node's body until its stop condition matches.

        Do-while semantics: the body always runs at least once before the
        stop condition is checked against its result.

        Args:
            session: Database session for every inner node this runs.
            run_context: Loop-invariant run context.
            node: The Loop node itself — `condition_type`/`value`/
                `case_sensitive` (same fields as the Condition node) decide
                when to stop.
            body_graph: The body's own validated `ExecutionGraphContext`.
            seed_text: The Loop node's upstream text, used as the first
                iteration's `LOOP_INPUT` value.

        Returns:
            The final iteration's `LOOP_OUTPUT` text as the Loop node's own
            output — marked as stopped-by-cap (not failed) if
            `MAX_LOOP_ITERATIONS` was reached without the condition matching.

        Raises:
            ExecutionGraphValidationError: If `condition_type` is
                unrecognized, or (for value-based condition types) `value`
                is empty, or it's an invalid `REGEX` pattern.
            BaseError: If an inner node fails — see `_run_loop_node`.

        """
        condition_type = self._read_loop_condition_type(node)
        case_sensitive = node.data.get("case_sensitive") == "true"
        raw_value = node.data.get("value")
        value = raw_value if isinstance(raw_value, str) else None

        current_text = seed_text
        for index in range(self._max_loop_iterations):
            iteration_context = replace(
                run_context, input_value=NodeValue.text(current_text)
            )
            body_outputs = await self._run_nodes_serial(
                session=session,
                run_context=iteration_context,
                graph=body_graph,
                iteration=index,
            )
            current_text = body_outputs[body_graph.output_node_id].require_text()

            if evaluate_condition(
                condition_type=condition_type,
                text=current_text,
                case_sensitive=case_sensitive,
                value=value,
            ):
                return NodeExecutionResult.text(current_text)

        marker = (
            f"\n\n[stopped: iteration cap ({self._max_loop_iterations}) reached "
            "without matching the stop condition]"
        )
        return NodeExecutionResult.text(f"{current_text}{marker}")

    def _read_loop_condition_type(self, node: NodeResponse) -> ConditionType:
        """Read and validate a Loop node's stop condition_type."""
        raw = node.data.get("condition_type")
        try:
            return ConditionType(raw)
        except ValueError as exc:
            message = f"Loop node {node.id} has an unsupported condition_type"
            raise ExecutionGraphValidationError(message=message) from exc

    @staticmethod
    def _make_on_token(run_context: _NodeRunContext, node_id: int) -> OnToken | None:
        """Build a per-node token callback bound to the run's publisher.

        Args:
            run_context: Loop-invariant run context.
            node_id: The node the tokens belong to.

        Returns:
            A token callback, or None when streaming is disabled.

        """
        publisher = run_context.token_publisher
        if publisher is None:
            return None

        async def on_token(delta: str) -> None:
            """Forward one token delta for this node to the publisher."""
            await publisher(run_context.execution_id, node_id, delta)

        return on_token

    async def _record_node_result(
        self,
        session: AsyncSession,
        run_context: _NodeRunContext,
        node: NodeResponse,
        started_at: datetime,
        outcome: _NodeOutcome,
    ) -> None:
        """Persist a single node's result row.

        Args:
            session: Database session.
            run_context: Loop-invariant run context.
            node: Executed node (from the graph snapshot).
            started_at: When the node started.
            outcome: The node's final status, output, error, and (if run
                inside a Loop node's body) iteration index.

        """
        stored_output = None
        output_value = None
        output_values = None
        if outcome.output is not None:
            output_value = outcome.output.to_payload()
            output_ports = get_node_definition(node.type).graph.outputs
            primary_name = output_ports[0].name if output_ports else "output"
            all_outputs = {primary_name: outcome.output, **(outcome.outputs or {})}
            output_values = {
                name: value.to_payload() for name, value in all_outputs.items()
            }
            if outcome.output.artifact is None:
                stored_output = outcome.output.to_legacy_text()
        await self._node_execution_repository.create(
            session=session,
            data={
                "execution_id": run_context.execution_id,
                "node_id": node.id,
                "node_type": node.type,
                "node_label": node.data.get("label"),
                "iteration": outcome.iteration,
                "status": outcome.status,
                "output": _truncate_for_storage(stored_output),
                "output_value": output_value,
                "output_values": output_values,
                "error": outcome.error,
                "prompt_tokens": (
                    outcome.usage.prompt_tokens if outcome.usage else None
                ),
                "completion_tokens": (
                    outcome.usage.completion_tokens if outcome.usage else None
                ),
                "total_tokens": (outcome.usage.total_tokens if outcome.usage else None),
                "started_at": started_at,
                "finished_at": datetime.now(tz=UTC),
            },
        )
        # A node just completed real work: bump the heartbeat so the reaper
        # can tell this run is still progressing, not stalled.
        await self._execution_repository.update_by(
            session=session,
            data={"heartbeat_at": datetime.now(tz=UTC)},
            id=run_context.execution_id,
        )
        await session.commit()

    def _retry_delay(self, attempt: int) -> float:
        """Compute exponential backoff delay for a retry attempt.

        Args:
            attempt: The 1-based attempt number that just failed.

        Returns:
            Delay in seconds before the next attempt.

        """
        return RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))

    async def _mark_execution_success(
        self,
        session: AsyncSession,
        execution_id: int,
        output_data: ExecutionOutputPayload,
    ) -> None:
        """Persist successful execution result (only if still RUNNING).

        Args:
            session: Database session.
            execution_id: Execution ID.
            output_data: Final output payload.

        """
        (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = await self._node_execution_repository.sum_tokens(
            session=session, execution_id=execution_id
        )
        won = await self._execution_repository.update_status_if(
            session=session,
            execution_id=execution_id,
            expected_status=ExecutionStatus.RUNNING,
            data={
                "status": ExecutionStatus.SUCCESS,
                "output_data": output_data.model_dump(),
                "error": None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "finished_at": datetime.now(tz=UTC),
            },
        )
        if not won:
            logger.warning(
                "Execution %s already finalized; skipping success write",
                execution_id,
            )

    async def _mark_execution_failed(
        self,
        session: AsyncSession,
        execution_id: int,
        error: str,
    ) -> None:
        """Persist failed execution result (only if still RUNNING).

        Args:
            session: Database session.
            execution_id: Execution ID.
            error: Failure reason.

        """
        (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = await self._node_execution_repository.sum_tokens(
            session=session, execution_id=execution_id
        )
        won = await self._execution_repository.update_status_if(
            session=session,
            execution_id=execution_id,
            expected_status=ExecutionStatus.RUNNING,
            data={
                "status": ExecutionStatus.FAILED,
                "error": error,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "finished_at": datetime.now(tz=UTC),
            },
        )
        if not won:
            logger.warning(
                "Execution %s already finalized; skipping failure write",
                execution_id,
            )

    def _build_graph_context(
        self,
        nodes: list[NodeResponse],
        edges: list[EdgeResponse],
        *,
        input_type: NodeType = NodeType.INPUT,
        output_type: NodeType = NodeType.OUTPUT,
    ) -> ExecutionGraphContext:
        """Build and validate graph context for execution.

        Args:
            nodes: The nodes in this one scope (already filtered — see
                `_build_scoped_graph_context`).
            edges: This scope's edges.
            input_type: The type that must appear exactly once as this
                scope's entry point — `INPUT` for the top-level graph,
                `LOOP_INPUT` for a Loop node's body.
            output_type: The type that must appear exactly once as this
                scope's exit point — `OUTPUT` for the top-level graph,
                `LOOP_OUTPUT` for a Loop node's body.

        Returns:
            Validated graph context.

        Raises:
            ExecutionGraphValidationError: If graph is invalid.

        """
        if not nodes:
            message = "Workflow must contain at least one node"
            raise ExecutionGraphValidationError(message=message)

        input_nodes = [node for node in nodes if node.type is input_type]
        if len(input_nodes) != 1:
            message = f"Workflow must contain exactly one {input_type.value} node"
            raise ExecutionGraphValidationError(message=message)

        output_nodes = [node for node in nodes if node.type is output_type]
        if len(output_nodes) != 1:
            message = f"Workflow must contain exactly one {output_type.value} node"
            raise ExecutionGraphValidationError(message=message)

        # Process nodes in a stable id order so graph traversal and parent-value
        # merging are deterministic across runs of the same workflow.
        ordered_nodes = sorted(nodes, key=lambda node: node.id)
        nodes_by_id = {node.id: node for node in ordered_nodes}
        adjacency = self._build_adjacency(
            ordered_nodes=ordered_nodes, edges=edges, nodes_by_id=nodes_by_id
        )

        topological_order = self._topological_order(
            indegree=adjacency.indegree, outbound=adjacency.outbound
        )
        input_node_id = input_nodes[0].id
        output_node_id = output_nodes[0].id
        self._validate_connectivity(
            input_node_id=input_node_id,
            output_node_id=output_node_id,
            outbound=adjacency.outbound,
            inbound=adjacency.inbound,
            nodes_by_id=nodes_by_id,
        )
        self._validate_approval_nodes(
            input_node_id=input_node_id,
            output_node_id=output_node_id,
            outbound=adjacency.outbound,
            nodes_by_id=nodes_by_id,
        )

        return ExecutionGraphContext(
            input_node_id=input_node_id,
            output_node_id=output_node_id,
            nodes_by_id=nodes_by_id,
            outbound=adjacency.outbound,
            inbound=adjacency.inbound,
            outbound_edges=adjacency.outbound_edges,
            inbound_edges=adjacency.inbound_edges,
            topological_order=topological_order,
        )

    def _validate_approval_nodes(
        self,
        input_node_id: int,
        output_node_id: int,
        outbound: dict[int, list[int]],
        nodes_by_id: dict[int, NodeResponse],
    ) -> None:
        """Require every approval node to gate every input-to-output path."""
        for node in nodes_by_id.values():
            if node.type is not NodeType.APPROVAL:
                continue
            reachable = self._collect_reachable(
                start_node_id=input_node_id,
                adjacency={
                    source_id: ([] if source_id == node.id else list(target_ids))
                    for source_id, target_ids in outbound.items()
                },
            )
            if output_node_id in reachable:
                raise ExecutionGraphValidationError(
                    message=("Approval node must be on every path from input to output")
                )

    def _build_adjacency(
        self,
        ordered_nodes: list[NodeResponse],
        edges: list[EdgeResponse],
        nodes_by_id: dict[int, NodeResponse],
    ) -> _Adjacency:
        """Build sorted adjacency maps (with per-edge source handles) and indegree.

        Args:
            ordered_nodes: Workflow nodes in stable id order.
            edges: Workflow edges.
            nodes_by_id: Nodes indexed by ID.

        Returns:
            The graph's adjacency maps and indegree count.

        Raises:
            ExecutionGraphValidationError: If an edge is malformed or its
                source/target ports are incompatible.

        """
        outbound: dict[int, list[int]] = {node.id: [] for node in ordered_nodes}
        inbound: dict[int, list[int]] = {node.id: [] for node in ordered_nodes}
        outbound_edges: dict[int, list[_RuntimeEdge]] = {
            node.id: [] for node in ordered_nodes
        }
        inbound_edges: dict[int, list[_RuntimeEdge]] = {
            node.id: [] for node in ordered_nodes
        }
        indegree: dict[int, int] = {node.id: 0 for node in ordered_nodes}
        for edge in edges:
            source_id = edge.source_node_id
            target_id = edge.target_node_id
            if source_id not in nodes_by_id or target_id not in nodes_by_id:
                message = "Workflow contains edge with missing node reference"
                raise ExecutionGraphValidationError(message=message)

            try:
                port_error = check_edge_ports(
                    nodes_by_id[source_id].type,
                    nodes_by_id[target_id].type,
                    source_data=nodes_by_id[source_id].data,
                    target_data=nodes_by_id[target_id].data,
                    source_handle=edge.source_handle,
                    target_handle=edge.target_handle,
                    coercion=edge.coercion,
                )
            except ValueError as exc:
                raise ExecutionGraphValidationError(message=str(exc)) from exc
            if port_error is not None:
                raise ExecutionGraphValidationError(message=port_error)

            outbound[source_id].append(target_id)
            inbound[target_id].append(source_id)
            edge_data = (
                target_id,
                edge.source_handle,
                edge.target_handle,
                edge.coercion,
            )
            outbound_edges[source_id].append(edge_data)
            inbound_edges[target_id].append(
                (
                    source_id,
                    edge.source_handle,
                    edge.target_handle,
                    edge.coercion,
                )
            )
            indegree[target_id] += 1

        self._validate_required_input_handles(
            ordered_nodes=ordered_nodes,
            inbound_edges=inbound_edges,
        )

        # Deterministic adjacency: parent merge order and wave order no longer
        # depend on edge-return order from the database.
        for neighbours in outbound.values():
            neighbours.sort()
        for parents in inbound.values():
            parents.sort()
        for neighbours_with_handle in outbound_edges.values():
            neighbours_with_handle.sort(key=lambda item: item[0])
        for parents_with_handle in inbound_edges.values():
            parents_with_handle.sort(key=lambda item: item[0])

        return _Adjacency(
            outbound=outbound,
            inbound=inbound,
            outbound_edges=outbound_edges,
            inbound_edges=inbound_edges,
            indegree=indegree,
        )

    def _validate_required_input_handles(
        self,
        ordered_nodes: list[NodeResponse],
        inbound_edges: dict[int, list[_RuntimeEdge]],
    ) -> None:
        """Require every non-optional declared input handle to be connected."""
        for node in ordered_nodes:
            input_ports = get_node_definition(node.type).graph.inputs
            if not input_ports:
                continue
            connected = {
                target_handle or input_ports[0].name
                for _, _, target_handle, _ in inbound_edges[node.id]
            }
            missing = [
                port.name
                for port in input_ports
                if port.required and port.name not in connected
            ]
            if missing:
                names = ", ".join(missing)
                raise ExecutionGraphValidationError(
                    message=(
                        f"Node {node.id} requires connected input handle(s): {names}"
                    )
                )

    def _topological_order(
        self,
        indegree: dict[int, int],
        outbound: dict[int, list[int]],
    ) -> list[int]:
        """Build topological order for workflow nodes.

        Args:
            indegree: Incoming edge count by node.
            outbound: Outbound adjacency map.

        Returns:
            Ordered node IDs.

        Raises:
            ExecutionGraphValidationError: If graph has a cycle.

        """
        queue: deque[int] = deque(
            node_id for node_id, node_indegree in indegree.items() if node_indegree == 0
        )
        order: list[int] = []
        seen_indegree = dict(indegree)
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for target_id in outbound[node_id]:
                seen_indegree[target_id] -= 1
                if seen_indegree[target_id] == 0:
                    queue.append(target_id)

        if len(order) != len(indegree):
            message = "Workflow graph must be acyclic"
            raise ExecutionGraphValidationError(message=message)

        return order

    def _validate_connectivity(
        self,
        input_node_id: int,
        output_node_id: int,
        outbound: dict[int, list[int]],
        inbound: dict[int, list[int]],
        nodes_by_id: dict[int, NodeResponse],
    ) -> None:
        """Validate that every node is on a path from input to output.

        Args:
            input_node_id: Input node ID.
            output_node_id: Output node ID.
            outbound: Outbound adjacency map.
            inbound: Inbound adjacency map.
            nodes_by_id: Workflow nodes by ID.

        Raises:
            ExecutionGraphValidationError: If graph contains disconnected nodes.

        """
        for node_id in nodes_by_id:
            if node_id not in self._collect_reachable(
                start_node_id=input_node_id, adjacency=outbound
            ) or node_id not in self._collect_reachable(
                start_node_id=output_node_id, adjacency=inbound
            ):
                message = "All workflow nodes must belong to input->output path"
                raise ExecutionGraphValidationError(message=message)

    def _collect_reachable(
        self,
        start_node_id: int,
        adjacency: dict[int, list[int]],
    ) -> set[int]:
        """Collect reachable nodes using DFS.

        Args:
            start_node_id: Start node ID.
            adjacency: Adjacency map.

        Returns:
            Set of reachable node IDs.

        """
        stack = [start_node_id]
        visited: set[int] = set()
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            stack.extend(adjacency[node_id])
        return visited

    def _extract_input_value(self, input_data: dict | None) -> NodeValue:
        """Extract text input for input node execution.

        Args:
            input_data: Execution input payload.

        Returns:
            Typed text input value.

        Raises:
            ExecutionInputValidationError: If payload is invalid.

        """
        if input_data is None:
            message = "Execution input payload is required"
            raise ExecutionInputValidationError(message=message)

        value = input_data.get("value")
        if not isinstance(value, str):
            message = "Execution input_data.value must be a string"
            raise ExecutionInputValidationError(message=message)

        return NodeValue.text(value)
