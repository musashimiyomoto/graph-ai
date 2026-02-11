"""Add prefect flow run ID to execution.

Revision ID: f6ef43be6f21
Revises: b608d77ba6c0
Create Date: 2026-02-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6ef43be6f21"
down_revision: str | None = "b608d77ba6c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        "executions",
        sa.Column(
            "prefect_flow_run_id",
            sa.Text(),
            nullable=True,
            comment="Prefect flow run ID",
        ),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column("executions", "prefect_flow_run_id")
