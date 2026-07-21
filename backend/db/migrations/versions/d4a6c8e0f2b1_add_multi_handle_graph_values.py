"""Add ordinary multi-handle graph values.

Revision ID: d4a6c8e0f2b1
Revises: c3f5a7b9d2e4
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a6c8e0f2b1"
down_revision: str | None = "c3f5a7b9d2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist target handles and per-handle node output envelopes."""
    op.add_column(
        "edges",
        sa.Column(
            "target_handle",
            sa.String(),
            nullable=True,
            comment="Named input handle on the target node (None = default handle)",
        ),
    )
    op.drop_constraint(
        "uq_edges_workflow_source_target",
        "edges",
        type_="unique",
    )
    op.create_index(
        "uq_edges_workflow_source_target_handles",
        "edges",
        [
            "workflow_id",
            "source_node_id",
            "target_node_id",
            sa.text("coalesce(source_handle, '')"),
            sa.text("coalesce(target_handle, '')"),
        ],
        unique=True,
    )
    op.add_column(
        "node_executions",
        sa.Column(
            "output_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Typed NodeValue envelopes keyed by declared output port name",
        ),
    )


def downgrade() -> None:
    """Remove ordinary multi-handle graph persistence."""
    op.drop_column("node_executions", "output_values")
    op.drop_index("uq_edges_workflow_source_target_handles", table_name="edges")
    op.create_unique_constraint(
        "uq_edges_workflow_source_target",
        "edges",
        ["workflow_id", "source_node_id", "target_node_id"],
    )
    op.drop_column("edges", "target_handle")
