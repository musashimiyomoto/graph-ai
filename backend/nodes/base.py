"""Base contracts for execution node handlers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.llm_provider import TokenUsage

OnToken = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class NodeExecutionContext:
    """Execution context passed to a node handler."""

    session: AsyncSession
    workflow_owner_id: int
    node_data: dict[str, object]
    parent_values: list[str]
    input_value: str
    on_token: OnToken | None = None


@dataclass(frozen=True)
class NodeExecutionResult:
    """Result of a single node handler execution.

    ``selected_handle`` is None for ordinary (single-output) nodes. Branching
    nodes (e.g. Condition) set it to the name of the one outbound edge handle
    that should carry the node's output onward; edges attached to any other
    handle are treated as not taken.

    ``usage`` carries token counts for nodes that call an LLM (None for every
    other node type), so the engine can record per-node cost and aggregate a
    per-run total.
    """

    output: str
    selected_handle: str | None = None
    usage: TokenUsage | None = None


class NodeHandler(Protocol):
    """Protocol for node handlers."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Execute node logic and return node output."""
