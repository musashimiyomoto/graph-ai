"""Add webhook execution source.

Revision ID: f0b3c6d9e2a5
Revises: e9a1c4d7b2f6
Create Date: 2026-07-17 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f0b3c6d9e2a5"
down_revision: str | None = "e9a1c4d7b2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE executionsource ADD VALUE IF NOT EXISTS 'WEBHOOK'")


def downgrade() -> None:
    """Keep the PostgreSQL enum value because it is unsafe to remove in-place."""
