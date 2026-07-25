"""Durable channel conversation model."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID
from enums import ExecutionSource


class Conversation(BaseWithID, BaseWithDate):
    """One workflow-scoped provider conversation or thread."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "channel",
            "external_thread",
            name="uq_conversations_workflow_channel_thread",
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
        comment="Workflow receiving this conversation",
    )
    channel: Mapped[ExecutionSource] = mapped_column(
        Enum(ExecutionSource),
        nullable=False,
        comment="Channel that owns the external thread identity",
    )
    external_thread: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="MD5 identity key for provider conversation and nested thread",
    )
    external_conversation_id: Mapped[str] = mapped_column(
        String(998),
        nullable=False,
        comment="Provider conversation identifier",
    )
    external_thread_id: Mapped[str | None] = mapped_column(
        String(998),
        comment="Optional nested provider thread identifier",
    )
    public_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        default=lambda: uuid4().hex,
        comment="Opaque bearer-safe session identifier",
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(320), comment="Latest normalized sender ID"
    )
    actor_display_name: Mapped[str | None] = mapped_column(
        String(320), comment="Latest normalized sender display name"
    )
    actor_address: Mapped[str | None] = mapped_column(
        String(998), comment="Latest normalized sender address"
    )
    locale: Mapped[str | None] = mapped_column(
        String(35), comment="Latest sender locale"
    )
    last_event_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Latest event observed for this conversation",
    )
