"""Execution model."""

from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text, func
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
        comment="Channel or mechanism that triggered this execution",
    )
    input_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Input data for execution"
    )
    output_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Output data from execution"
    )
    error: Mapped[str | None] = mapped_column(Text, comment="Error message if failed")
    approval_node_id: Mapped[int | None] = mapped_column(
        comment="Node awaiting an owner approval decision"
    )
    approval_prompt: Mapped[str | None] = mapped_column(
        Text, comment="Human-readable approval request"
    )
    approval_input: Mapped[str | None] = mapped_column(
        Text, comment="Upstream value awaiting approval"
    )
    queue_job_id: Mapped[str | None] = mapped_column(
        String(255), comment="Current ARQ job ID for cancellation/resume"
    )
    wait_until: Mapped[datetime | None] = mapped_column(
        comment="Earliest durable Delay checkpoint wake-up time"
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="Telegram chat to reply to, if this run was triggered by a message",
    )
    email_reply_to: Mapped[str | None] = mapped_column(
        String(320), comment="Sender address to reply to for email-triggered runs"
    )
    email_subject: Mapped[str | None] = mapped_column(
        String(998), comment="Subject of the email that triggered this run"
    )

    # Run-level token totals, summed across every LLM node in the run. NULL
    # until the run finalizes (and stays 0 for a run with no LLM nodes).
    prompt_tokens: Mapped[int | None] = mapped_column(
        comment="Total LLM prompt tokens across the run"
    )
    completion_tokens: Mapped[int | None] = mapped_column(
        comment="Total LLM completion tokens across the run"
    )
    total_tokens: Mapped[int | None] = mapped_column(
        comment="Total LLM tokens across the run"
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
