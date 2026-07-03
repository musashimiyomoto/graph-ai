"""Node execution model."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID
from enums import ExecutionStatus


class NodeExecution(BaseWithID):
    """Per-node result captured while running a workflow execution."""

    __tablename__ = "node_executions"

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent execution ID",
    )
    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Executed node ID",
    )

    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus),
        nullable=False,
        comment="Node execution status",
    )
    output: Mapped[str | None] = mapped_column(
        Text, comment="Node output text if the node succeeded"
    )
    error: Mapped[str | None] = mapped_column(
        Text, comment="Error message if the node failed"
    )

    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Node execution start time",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        comment="Node execution end time"
    )
