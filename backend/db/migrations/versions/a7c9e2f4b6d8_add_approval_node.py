"""Add approval node and execution pause state.

Revision ID: a7c9e2f4b6d8
Revises: f6b8c1d4e7a9
Create Date: 2026-07-19 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e2f4b6d8"
down_revision: str | None = "f6b8c1d4e7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add approval lifecycle values and execution checkpoint metadata."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'APPROVAL'")
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'WAITING_APPROVAL'")
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.add_column("executions", sa.Column("approval_node_id", sa.Integer()))
    op.add_column("executions", sa.Column("approval_prompt", sa.Text()))
    op.add_column("executions", sa.Column("approval_input", sa.Text()))
    op.add_column("executions", sa.Column("queue_job_id", sa.String(length=255)))


def downgrade() -> None:
    """Drop columns while retaining PostgreSQL enum values."""
    op.drop_column("executions", "queue_job_id")
    op.drop_column("executions", "approval_input")
    op.drop_column("executions", "approval_prompt")
    op.drop_column("executions", "approval_node_id")
