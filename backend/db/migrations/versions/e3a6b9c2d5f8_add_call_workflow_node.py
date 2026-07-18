"""Add Call Workflow node type.

Revision ID: e3a6b9c2d5f8
Revises: d2f5a8c1e4b7
Create Date: 2026-07-18 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3a6b9c2d5f8"
down_revision: str | None = "d2f5a8c1e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the enum value."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'CALL_WORKFLOW'")


def downgrade() -> None:
    """Keep the PostgreSQL enum value because it is unsafe to remove in-place."""
