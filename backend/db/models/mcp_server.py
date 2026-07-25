"""Saved MCP server model."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class MCPServer(BaseWithID):
    """A reusable user-owned remote MCP server configuration."""

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_mcp_servers_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Unified credential connection ID",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
