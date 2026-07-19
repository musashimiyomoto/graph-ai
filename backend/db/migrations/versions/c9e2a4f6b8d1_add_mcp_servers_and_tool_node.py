"""Add saved MCP servers and MCP Tool node.

Revision ID: c9e2a4f6b8d1
Revises: b8d1f3a5c7e9
Create Date: 2026-07-19 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e2a4f6b8d1"
down_revision: str | None = "b8d1f3a5c7e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create MCP server storage and add the node enum value."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'MCP_TOOL'")
    op.create_table(
        "mcp_servers",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("headers", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "name",
            name="uq_mcp_servers_user_name",
        ),
    )
    op.create_index(
        op.f("ix_mcp_servers_user_id"),
        "mcp_servers",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop MCP server storage while retaining the PostgreSQL enum value."""
    op.drop_index(op.f("ix_mcp_servers_user_id"), table_name="mcp_servers")
    op.drop_table("mcp_servers")
