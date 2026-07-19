"""Sync recent model metadata.

Revision ID: e2a4c6f8b1d3
Revises: d1f3a5c7e9b2
Create Date: 2026-07-19 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a4c6f8b1d3"
down_revision: str | None = "d1f3a5c7e9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Bring recent table definitions in line with their models."""
    op.alter_column(
        "auth_sessions",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="ID",
    )
    op.alter_column(
        "auth_sessions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text("now()"),
        nullable=False,
        comment="Created at",
    )
    op.alter_column(
        "auth_sessions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text("now()"),
        nullable=False,
        comment="Updated at",
    )
    op.drop_constraint(
        "auth_sessions_token_hash_key",
        "auth_sessions",
        type_="unique",
    )

    op.alter_column(
        "executions",
        "approval_node_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
        comment="Node awaiting an owner approval decision",
    )
    op.alter_column(
        "executions",
        "approval_prompt",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="Human-readable approval request",
    )
    op.alter_column(
        "executions",
        "approval_input",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="Upstream value awaiting approval",
    )
    op.alter_column(
        "executions",
        "queue_job_id",
        existing_type=sa.String(length=255),
        existing_nullable=True,
        comment="Current ARQ job ID for cancellation/resume",
    )

    op.alter_column(
        "mcp_servers",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="ID",
    )
    op.alter_column(
        "mcp_servers",
        "user_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="Owner user ID",
    )
    op.alter_column(
        "mcp_servers",
        "headers",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment="Encrypted JSON HTTP headers",
    )


def downgrade() -> None:
    """Restore the schema metadata from the preceding revisions."""
    op.alter_column(
        "mcp_servers",
        "headers",
        existing_type=sa.Text(),
        existing_nullable=False,
        comment=None,
    )
    op.alter_column(
        "mcp_servers",
        "user_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment=None,
    )
    op.alter_column(
        "mcp_servers",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment=None,
    )

    op.alter_column(
        "executions",
        "queue_job_id",
        existing_type=sa.String(length=255),
        existing_nullable=True,
        comment=None,
    )
    op.alter_column(
        "executions",
        "approval_input",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment=None,
    )
    op.alter_column(
        "executions",
        "approval_prompt",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment=None,
    )
    op.alter_column(
        "executions",
        "approval_node_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
        comment=None,
    )

    op.create_unique_constraint(
        "auth_sessions_token_hash_key",
        "auth_sessions",
        ["token_hash"],
    )
    op.alter_column(
        "auth_sessions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        nullable=True,
        comment=None,
    )
    op.alter_column(
        "auth_sessions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        nullable=True,
        comment=None,
    )
    op.alter_column(
        "auth_sessions",
        "id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment=None,
    )
