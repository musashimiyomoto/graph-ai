"""Add tenant artifacts and typed node output envelopes.

Revision ID: b2e4f6a8c1d3
Revises: a1d3f5b7c9e2
Create Date: 2026-07-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2e4f6a8c1d3"
down_revision: str | None = "a1d3f5b7c9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create artifact metadata and persist complete NodeValue envelopes."""
    op.create_table(
        "artifacts",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owning user ID"),
        sa.Column(
            "object_key",
            sa.String(length=1024),
            nullable=False,
            comment="Tenant-scoped object-storage key",
        ),
        sa.Column(
            "filename",
            sa.String(length=255),
            nullable=False,
            comment="Original sanitized filename",
        ),
        sa.Column(
            "mime_type",
            sa.String(length=255),
            nullable=False,
            comment="Declared content MIME type",
        ),
        sa.Column(
            "size", sa.BigInteger(), nullable=False, comment="Artifact size in bytes"
        ),
        sa.Column(
            "checksum",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 content checksum",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Retention deadline; NULL means retain indefinitely",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Created at",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Updated at",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("user_id", "checksum", name="uq_artifacts_user_checksum"),
    )
    op.create_index("ix_artifacts_checksum", "artifacts", ["checksum"])
    op.create_index("ix_artifacts_expires_at", "artifacts", ["expires_at"])
    op.create_index("ix_artifacts_user_id", "artifacts", ["user_id"])
    op.add_column(
        "node_executions",
        sa.Column(
            "output_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Typed NodeValue envelope; NULL for legacy checkpoint rows",
        ),
    )


def downgrade() -> None:
    """Drop typed envelopes and artifact metadata."""
    op.drop_column("node_executions", "output_value")
    op.drop_index("ix_artifacts_user_id", table_name="artifacts")
    op.drop_index("ix_artifacts_expires_at", table_name="artifacts")
    op.drop_index("ix_artifacts_checksum", table_name="artifacts")
    op.drop_table("artifacts")
