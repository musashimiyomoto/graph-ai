"""Add template and http_request node types.

Revision ID: c7d2f1a9b3e4
Revises: 709163b05319
Create Date: 2026-07-03 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d2f1a9b3e4"
down_revision: str | None = "709163b05319"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'TEMPLATE'")
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'HTTP_REQUEST'")


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are not safely removable in-place, so this is a no-op.
    """
