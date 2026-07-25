"""Tenant-owned logical knowledge collection model."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID


class KnowledgeCollection(BaseWithID, BaseWithDate):
    """Logical collection mapped to one opaque tenant Qdrant namespace."""

    __tablename__ = "knowledge_collections"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "name", name="uq_knowledge_collections_owner_name"
        ),
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant owner ID",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Owner-visible logical collection name"
    )
    physical_name: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        unique=True,
        comment="Opaque tenant-specific Qdrant collection name",
    )
    sync_cursor: Mapped[str | None] = mapped_column(
        String(2048), comment="Opaque incremental connector cursor"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        index=True, comment="Latest successful connector synchronization"
    )
