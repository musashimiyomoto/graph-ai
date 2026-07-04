"""Add workflow versions.

Revision ID: e4f1a9c2b7d8
Revises: d3e5a7c1f9b2
Create Date: 2026-07-03 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4f1a9c2b7d8"
down_revision: str | None = "d3e5a7c1f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "version", name="uq_workflow_versions_number"
        ),
    )
    op.create_index(
        "ix_workflow_versions_workflow_id",
        "workflow_versions",
        ["workflow_id"],
    )
    op.add_column(
        "executions",
        sa.Column("version_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_executions_version_id", "executions", ["version_id"])
    op.create_foreign_key(
        "fk_executions_version_id",
        "executions",
        "workflow_versions",
        ["version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_constraint("fk_executions_version_id", "executions", type_="foreignkey")
    op.drop_index("ix_executions_version_id", table_name="executions")
    op.drop_column("executions", "version_id")
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")
