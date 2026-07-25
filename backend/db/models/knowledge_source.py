"""Durable knowledge source metadata model."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID


class KnowledgeSource(BaseWithID, BaseWithDate):
    """One revisioned document/source inside a tenant collection."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint(
            "collection_id", "source", name="uq_knowledge_sources_collection_source"
        ),
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant owner ID",
    )
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning logical collection",
    )
    source: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Stable source key within the collection"
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="upload",
        server_default="upload",
        comment="Connector/source adapter key",
    )
    external_id: Mapped[str | None] = mapped_column(
        String(1024), comment="Provider-native stable object ID"
    )
    revision: Mapped[str | None] = mapped_column(
        String(512), comment="Provider revision/version used for incremental sync"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 of normalized extracted text"
    )
    acl: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Provider-neutral visibility and reader principals",
    )
    source_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Bounded non-secret connector metadata",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Current Qdrant chunk count",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        index=True, comment="Optional retention deadline"
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        index=True, comment="Latest successful source synchronization"
    )
