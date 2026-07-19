"""Add cancelled execution status.

Revision ID: f6b8c1d4e7a9
Revises: e3a6b9c2d5f8
Create Date: 2026-07-19 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6b8c1d4e7a9"
down_revision: str | None = "e3a6b9c2d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the enum value."""
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    """Keep the PostgreSQL enum value because it is unsafe to remove in-place."""
