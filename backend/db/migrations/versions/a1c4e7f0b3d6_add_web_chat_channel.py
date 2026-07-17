"""Add web-chat execution source.

Revision ID: a1c4e7f0b3d6
Revises: f0b3c6d9e2a5
Create Date: 2026-07-18 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c4e7f0b3d6"
down_revision: str | None = "f0b3c6d9e2a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE executionsource ADD VALUE IF NOT EXISTS 'WEB_CHAT'")


def downgrade() -> None:
    """Keep the PostgreSQL enum value because it is unsafe to remove in-place."""
