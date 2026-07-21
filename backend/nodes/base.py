"""Base contracts for execution node handlers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from nodes.value import NodeValue
from schemas.llm_provider import TokenUsage

OnToken = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class NodeExecutionContext:
    """Execution context passed to a node handler."""

    session: AsyncSession
    workflow_owner_id: int
    node_data: dict[str, object]
    parent_values: list[NodeValue]
    input_value: NodeValue
    on_token: OnToken | None = None

    @property
    def parent_texts(self) -> list[str]:
        """Return all parent values as validated text values."""
        return [value.require_text() for value in self.parent_values]

    @property
    def input_text(self) -> str:
        """Return the execution input as validated text."""
        return self.input_value.require_text()

    def joined_parent_text(self, separator: str = "\n") -> str:
        """Join validated parent text in deterministic parent order."""
        return separator.join(self.parent_texts)


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

    output: NodeValue
    selected_handle: str | None = None
    usage: TokenUsage | None = None

    @classmethod
    def text(
        cls,
        output: str,
        *,
        selected_handle: str | None = None,
        usage: TokenUsage | None = None,
    ) -> "NodeExecutionResult":
        """Build a text result for an existing text-output handler."""
        return cls(
            output=NodeValue.text(output),
            selected_handle=selected_handle,
            usage=usage,
        )


class NodeHandler(Protocol):
    """Protocol for node handlers."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Execute node logic and return node output."""
