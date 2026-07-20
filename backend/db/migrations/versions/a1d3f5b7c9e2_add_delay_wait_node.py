"""Add durable Delay / Wait node checkpoints.

Revision ID: a1d3f5b7c9e2
Revises: f7c9e1a3b5d8
Create Date: 2026-07-20 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d3f5b7c9e2"
down_revision: str | None = "f7c9e1a3b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Delay lifecycle values and wake-up timestamps."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'DELAY'")
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'WAITING_DELAY'")
    op.add_column(
        "executions",
        sa.Column(
            "wait_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Earliest durable Delay checkpoint wake-up time",
        ),
    )
    op.add_column(
        "node_executions",
        sa.Column(
            "wait_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Durable Delay checkpoint wake-up time",
        ),
    )


def downgrade() -> None:
    """Drop wake-up columns while retaining PostgreSQL enum values."""
    op.drop_column("node_executions", "wait_until")
    op.drop_column("executions", "wait_until")
