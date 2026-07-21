"""Tenant-owned workflow artifact metadata model."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID


class Artifact(BaseWithID, BaseWithDate):
    """Metadata for immutable bytes stored in S3-compatible object storage."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("user_id", "checksum", name="uq_artifacts_user_checksum"),
        Index("ix_artifacts_expires_at", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning user ID",
    )
    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
        comment="Tenant-scoped object-storage key",
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Original sanitized filename"
    )
    mime_type: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Declared content MIME type"
    )
    size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Artifact size in bytes"
    )
    checksum: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="SHA-256 content checksum"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        comment="Retention deadline; NULL means retain indefinitely"
    )
