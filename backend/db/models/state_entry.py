"""Typed durable state model."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID
from enums import StateScope


class StateEntry(BaseWithID, BaseWithDate):
    """Current typed value for one workflow-scoped state key."""

    __tablename__ = "state_entries"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "scope",
            "scope_ref",
            "key",
            name="uq_state_entries_workflow_scope_ref_key",
        ),
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant owner ID",
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Workflow boundary for every state scope",
    )
    scope: Mapped[StateScope] = mapped_column(
        Enum(StateScope), nullable=False, comment="State lifetime scope"
    )
    scope_ref: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Resolved execution/conversation/user ID"
    )
    key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Application-defined state key"
    )
    value: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="Serialized NodeValue envelope"
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Monotonic optimistic-concurrency version",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        index=True, comment="Optional UTC expiry time"
    )


class StateEntryHistory(BaseWithID):
    """Append-only audit history for state mutations, including deletes."""

    __tablename__ = "state_entry_history"

    state_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("state_entries.id", ondelete="SET NULL"),
        index=True,
        comment="Current row when it still exists",
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant owner ID",
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Workflow boundary at mutation time",
    )
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"),
        index=True,
        comment="Execution whose context authorized the mutation",
    )
    scope: Mapped[StateScope] = mapped_column(
        Enum(StateScope), nullable=False, comment="State lifetime scope"
    )
    scope_ref: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Resolved scope identity"
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False, comment="State key")
    operation: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="create, update, or delete"
    )
    value: Mapped[dict | None] = mapped_column(
        JSONB, comment="Typed value after mutation, or deleted value"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="State version affected by this mutation"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        comment="Expiry configured by this mutation"
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Mutation time",
    )
