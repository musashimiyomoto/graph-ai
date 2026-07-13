"""Add node schedules.

Revision ID: 7e59dce05344
Revises: c9e4b1a7d3f6
Create Date: 2026-07-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e59dce05344"
down_revision: str | None = "c9e4b1a7d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE executionsource ADD VALUE IF NOT EXISTS 'SCHEDULE'")
    op.create_table(
        "node_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("cron_expression", sa.Text(), nullable=False),
        sa.Column(
            "last_fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", name="uq_node_schedules_node_id"),
    )


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are not safely removable in-place, so the
    ``executionsource`` addition above is a no-op here.
    """
    op.drop_table("node_schedules")
