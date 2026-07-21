"""Add explicit typed-value coercions to workflow edges.

Revision ID: c3f5a7b9d2e4
Revises: b2e4f6a8c1d3
Create Date: 2026-07-21 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f5a7b9d2e4"
down_revision: str | None = "b2e4f6a8c1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store an optional declared conversion on every edge."""
    op.add_column(
        "edges",
        sa.Column(
            "coercion",
            sa.String(length=64),
            nullable=True,
            comment=(
                "Explicit typed-value conversion applied while traversing the edge"
            ),
        ),
    )


def downgrade() -> None:
    """Remove explicit edge conversion metadata."""
    op.drop_column("edges", "coercion")
