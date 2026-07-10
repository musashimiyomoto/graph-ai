"""Execution model."""

from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID
from enums import ExecutionSource, ExecutionStatus


class Execution(BaseWithID):
    """Workflow execution record."""

    __tablename__ = "executions"

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent workflow ID",
    )
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Pinned workflow version snapshot",
    )

    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus),
        default=ExecutionStatus.CREATED,
        comment="Execution status",
    )
    source: Mapped[ExecutionSource] = mapped_column(
        Enum(ExecutionSource),
        default=ExecutionSource.MANUAL,
        server_default=ExecutionSource.MANUAL.name,
        nullable=False,
        comment="What triggered this execution (manual test run vs Telegram traffic)",
    )
    input_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Input data for execution"
    )
    output_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Output data from execution"
    )
    error: Mapped[str | None] = mapped_column(Text, comment="Error message if failed")
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="Telegram chat to reply to, if this run was triggered by a message",
    )

    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Execution start time",
    )
    finished_at: Mapped[datetime | None] = mapped_column(comment="Execution end time")
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        comment=(
            "Last node-completion time, bumped as the run progresses so the "
            "stuck-execution reaper can tell a long-but-active run from one "
            "that's actually stalled"
        )
    )
