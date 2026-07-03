"""Index foreign-key columns.

Revision ID: d3e5a7c1f9b2
Revises: c7d2f1a9b3e4
Create Date: 2026-07-03 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e5a7c1f9b2"
down_revision: str | None = "c7d2f1a9b3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table, column) for every foreign key.
_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_workflows_owner_id", "workflows", "owner_id"),
    ("ix_nodes_workflow_id", "nodes", "workflow_id"),
    ("ix_edges_workflow_id", "edges", "workflow_id"),
    ("ix_edges_source_node_id", "edges", "source_node_id"),
    ("ix_edges_target_node_id", "edges", "target_node_id"),
    ("ix_executions_workflow_id", "executions", "workflow_id"),
    ("ix_node_executions_execution_id", "node_executions", "execution_id"),
    ("ix_node_executions_node_id", "node_executions", "node_id"),
    ("ix_llm_providers_user_id", "llm_providers", "user_id"),
)


def upgrade() -> None:
    """Upgrade database schema."""
    for name, table, column in _INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    """Downgrade database schema."""
    for name, table, _column in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
