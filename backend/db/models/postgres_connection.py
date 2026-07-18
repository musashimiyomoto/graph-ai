"""Saved PostgreSQL connection model."""

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class PostgresConnection(BaseWithID):
    """A reusable, user-owned encrypted PostgreSQL connection."""

    __tablename__ = "postgres_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_postgres_connections_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Connection display name"
    )
    dsn: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Encrypted PostgreSQL DSN"
    )
