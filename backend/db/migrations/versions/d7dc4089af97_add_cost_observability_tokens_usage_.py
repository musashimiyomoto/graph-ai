"""Add cost observability: token columns, usage records, and audit logs.

Revision ID: d7dc4089af97
Revises: 811e4da3868d
Create Date: 2026-07-16 12:44:53.947514

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d7dc4089af97"
down_revision: str | None = "811e4da3868d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXEC_TOKEN_COLUMNS = (
    ("prompt_tokens", "Total LLM prompt tokens across the run"),
    ("completion_tokens", "Total LLM completion tokens across the run"),
    ("total_tokens", "Total LLM tokens across the run"),
)
_NODE_TOKEN_COLUMNS = (
    ("prompt_tokens", "LLM prompt/input tokens, if this node called an LLM"),
    ("completion_tokens", "LLM completion/output tokens, if this node called an LLM"),
    ("total_tokens", "LLM total tokens, if this node called an LLM"),
)


def upgrade() -> None:
    """Upgrade database schema."""
    for name, comment in _EXEC_TOKEN_COLUMNS:
        op.add_column(
            "executions",
            sa.Column(name, sa.Integer(), nullable=True, comment=comment),
        )
    for name, comment in _NODE_TOKEN_COLUMNS:
        op.add_column(
            "node_executions",
            sa.Column(name, sa.Integer(), nullable=True, comment=comment),
        )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "period_start",
            sa.Date(),
            nullable=False,
            comment="First day of the usage window (UTC calendar day)",
        ),
        sa.Column(
            "executions_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Executions finalized in this window",
        ),
        sa.Column(
            "total_tokens",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="LLM tokens consumed in this window",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "period_start", name="uq_usage_records_user_period"
        ),
    )
    op.create_index(
        op.f("ix_usage_records_user_id"), "usage_records", ["user_id"], unique=False
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Acting user ID"),
        sa.Column(
            "action",
            sa.String(length=64),
            nullable=False,
            comment="Action name, e.g. 'execution.create' or 'workflow.delete'",
        ),
        sa.Column(
            "entity_type",
            sa.String(length=64),
            nullable=False,
            comment="Affected entity type, e.g. 'execution', 'workflow'",
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=True,
            comment="Affected entity ID, if the action targets a specific row",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra structured context for the action",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the action occurred",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_usage_records_user_id"), table_name="usage_records")
    op.drop_table("usage_records")
    for name, _ in _NODE_TOKEN_COLUMNS:
        op.drop_column("node_executions", name)
    for name, _ in _EXEC_TOKEN_COLUMNS:
        op.drop_column("executions", name)
