"""Execution model."""

from datetime import datetime

from backend.enums import ExecutionStatus
from backend.models import BaseWithID
from sqlalchemy import Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Execution(BaseWithID):
    """Workflow execution record."""

    __tablename__ = "executions"

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent workflow ID",
    )

    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus),
        default=ExecutionStatus.CREATED,
        comment="Execution status",
    )
    input_data: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="Input data for execution",
    )
    output_data: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="Output data from execution",
    )
    error: Mapped[str | None] = mapped_column(Text, comment="Error message if failed")

    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Execution start time",
    )
    finished_at: Mapped[datetime | None] = mapped_column(comment="Execution end time")
