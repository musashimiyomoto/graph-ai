"""Add Switch node type.

Revision ID: b8d1f3a5c7e9
Revises: a7c9e2f4b6d8
Create Date: 2026-07-19 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8d1f3a5c7e9"
down_revision: str | None = "a7c9e2f4b6d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Switch node enum value."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'SWITCH'")


def downgrade() -> None:
    """Retain the PostgreSQL enum value because it cannot be safely removed."""
