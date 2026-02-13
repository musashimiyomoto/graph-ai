"""Add web_search node type.

Revision ID: 7f6f03f7f3a3
Revises: b608d77ba6c0
Create Date: 2026-02-13 19:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f6f03f7f3a3"
down_revision: str | None = "b608d77ba6c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'WEB_SEARCH'")


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are not safely removable in-place, so this is a no-op.
    """
