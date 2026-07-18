"""Add Table node and saved PostgreSQL connections.

Revision ID: d2f5a8c1e4b7
Revises: a1c4e7f0b3d6
Create Date: 2026-07-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f5a8c1e4b7"
down_revision: str | None = "a1c4e7f0b3d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'TABLE'")
    op.create_table(
        "postgres_connections",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="Connection display name",
        ),
        sa.Column("dsn", sa.Text(), nullable=False, comment="Encrypted PostgreSQL DSN"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "name", name="uq_postgres_connections_user_name"
        ),
    )
    op.create_index(
        op.f("ix_postgres_connections_user_id"),
        "postgres_connections",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop connection storage; keep the PostgreSQL enum value in place."""
    op.drop_index(
        op.f("ix_postgres_connections_user_id"),
        table_name="postgres_connections",
    )
    op.drop_table("postgres_connections")
