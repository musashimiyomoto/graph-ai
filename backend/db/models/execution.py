"""Execution model."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
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
    version_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Pinned workflow version snapshot",
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Durable normalized conversation for this run",
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
    trigger_event: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Versioned provider-neutral event that triggered this execution",
    )
    trigger_external_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Denormalized external trigger ID used for idempotency",
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
    heartbeat_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment=(
            "Last execution progress time, bumped as the run progresses so the "
            "stuck-execution reaper can tell a long-but-active run from one "
            "that's actually stalled"
        ),
    )


Index(
    "uq_executions_trigger_external_event",
    Execution.workflow_id,
    Execution.source,
    Execution.trigger_external_id,
    unique=True,
    postgresql_where=Execution.trigger_external_id.is_not(None),
)
