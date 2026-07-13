"""Add loop node type and scoping.

Revision ID: 3d86d4967e16
Revises: 7e59dce05344
Create Date: 2026-07-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d86d4967e16"
down_revision: str | None = "7e59dce05344"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'LOOP'")
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'LOOP_INPUT'")
    op.execute("ALTER TYPE nodetype ADD VALUE IF NOT EXISTS 'LOOP_OUTPUT'")
    op.add_column(
        "nodes",
        sa.Column(
            "parent_node_id",
            sa.Integer(),
            nullable=True,
            comment="Owning Loop node's id, or NULL for a top-level graph node",
        ),
    )
    op.create_foreign_key(
        "fk_nodes_parent_node_id",
        "nodes",
        "nodes",
        ["parent_node_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_nodes_parent_node_id", "nodes", ["parent_node_id"])
    op.add_column(
        "node_executions",
        sa.Column(
            "iteration",
            sa.Integer(),
            nullable=True,
            comment="Loop iteration index (0-based); NULL for a top-level node",
        ),
    )


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are not safely removable in-place, so only the
    added columns/constraints are dropped.
    """
    op.drop_column("node_executions", "iteration")
    op.drop_index("ix_nodes_parent_node_id", table_name="nodes")
    op.drop_constraint("fk_nodes_parent_node_id", "nodes", type_="foreignkey")
    op.drop_column("nodes", "parent_node_id")
