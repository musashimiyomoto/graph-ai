"""Add Translate node type.

Revision ID: f7c9e1a3b5d8
Revises: e5b7c9d1f3a6
Create Date: 2026-07-20 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f7c9e1a3b5d8"
down_revision: str | None = "e5b7c9d1f3a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Translate node enum value."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'TRANSLATE'")


def downgrade() -> None:
    """Retain the PostgreSQL enum value because it cannot be safely removed."""
