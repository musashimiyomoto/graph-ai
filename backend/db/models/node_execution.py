"""Node execution model."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID
from enums import ExecutionStatus, NodeType


class NodeExecution(BaseWithID):
    """Per-node result captured while running a workflow execution."""

    __tablename__ = "node_executions"

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent execution ID",
    )
    # Deliberately not a foreign key: a pinned execution can rerun a
    # workflow-version snapshot referencing a node since deleted from the
    # live `nodes` table. Kept as a plain historical reference so recording
    # a result never fails, and so deleting a node no longer collaterally
    # deletes its (unrelated) execution history via cascade.
    node_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
        comment="Executed node ID (not FK-enforced; the node may since be deleted)",
    )
    # Denormalized from the node at execution time, so the result stays
    # meaningful even after the live node is edited or deleted.
    node_type: Mapped[NodeType | None] = mapped_column(
        Enum(NodeType),
        comment="Node type at execution time (denormalized snapshot)",
    )
    node_label: Mapped[str | None] = mapped_column(
        Text, comment="Node label at execution time (denormalized snapshot)"
    )
    iteration: Mapped[int | None] = mapped_column(
        comment="Loop iteration index (0-based); NULL for a top-level node"
    )

    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus),
        nullable=False,
        comment="Node execution status",
    )
    output: Mapped[str | None] = mapped_column(
        Text, comment="Node output text if the node succeeded"
    )
    output_value: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="Typed NodeValue envelope; NULL for legacy checkpoint rows",
    )
    error: Mapped[str | None] = mapped_column(
        Text, comment="Error message if the node failed"
    )

    # Token usage for nodes that call an LLM; NULL for node types that never
    # do (Input, Template, HTTP, etc.) so "no LLM call" is distinguishable
    # from "an LLM call that reported zero tokens".
    prompt_tokens: Mapped[int | None] = mapped_column(
        comment="LLM prompt/input tokens, if this node called an LLM"
    )
    completion_tokens: Mapped[int | None] = mapped_column(
        comment="LLM completion/output tokens, if this node called an LLM"
    )
    total_tokens: Mapped[int | None] = mapped_column(
        comment="LLM total tokens, if this node called an LLM"
    )

    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Node execution start time",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        comment="Node execution end time"
    )
    wait_until: Mapped[datetime | None] = mapped_column(
        comment="Durable Delay checkpoint wake-up time"
    )
