"""Append-only audit log model."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithID


class AuditLog(BaseWithID):
    """One append-only record of a tenant-visible mutating action.

    Written from the mutating usecases (execution create, workflow/provider/bot
    create+delete) so a tenant has a durable trail of what changed and when,
    independent of the mutated rows themselves (which may since be deleted).
    """

    __tablename__ = "audit_logs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Acting user ID",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Action name, e.g. 'execution.create' or 'workflow.delete'",
    )
    entity_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Affected entity type, e.g. 'execution', 'workflow'",
    )
    entity_id: Mapped[int | None] = mapped_column(
        comment="Affected entity ID, if the action targets a specific row"
    )
    audit_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="Extra structured context for the action",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        index=True,
        comment="When the action occurred",
    )
