"""Base contracts for execution node handlers."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class NodeExecutionContext:
    """Execution context passed to a node handler."""

    session: AsyncSession
    workflow_owner_id: int
    node_data: dict[str, object]
    parent_values: list[str]
    input_value: str


class NodeHandler(Protocol):
    """Protocol for node handlers."""

    async def execute(self, context: NodeExecutionContext) -> str:
        """Execute node logic and return node output."""
