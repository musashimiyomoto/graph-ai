"""Add tenant knowledge collection and source registries.

Revision ID: b0d3f5a7c9e1
Revises: a9c2e4f6b8d0
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0d3f5a7c9e1"
down_revision: str | None = "a9c2e4f6b8d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tenant collection mappings and revisioned source metadata."""
    op.create_table(
        "knowledge_collections",
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Tenant owner ID"),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Owner-visible logical collection name",
        ),
        sa.Column(
            "physical_name",
            sa.String(length=96),
            nullable=False,
            comment="Opaque tenant-specific Qdrant collection name",
        ),
        sa.Column(
            "sync_cursor",
            sa.String(length=2048),
            nullable=True,
            comment="Opaque incremental connector cursor",
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Latest successful connector synchronization",
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("physical_name"),
        sa.UniqueConstraint(
            "owner_id", "name", name="uq_knowledge_collections_owner_name"
        ),
    )
    op.create_index(
        "ix_knowledge_collections_last_synced_at",
        "knowledge_collections",
        ["last_synced_at"],
    )
    op.create_index(
        "ix_knowledge_collections_owner_id", "knowledge_collections", ["owner_id"]
    )

    op.create_table(
        "knowledge_sources",
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Tenant owner ID"),
        sa.Column(
            "collection_id",
            sa.Integer(),
            nullable=False,
            comment="Owning logical collection",
        ),
        sa.Column(
            "source",
            sa.String(length=512),
            nullable=False,
            comment="Stable source key within the collection",
        ),
        sa.Column(
            "source_type",
            sa.String(length=64),
            server_default="upload",
            nullable=False,
            comment="Connector/source adapter key",
        ),
        sa.Column(
            "external_id",
            sa.String(length=1024),
            nullable=True,
            comment="Provider-native stable object ID",
        ),
        sa.Column(
            "revision",
            sa.String(length=512),
            nullable=True,
            comment="Provider revision/version used for incremental sync",
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 of normalized extracted text",
        ),
        sa.Column(
            "acl",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Provider-neutral visibility and reader principals",
        ),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Bounded non-secret connector metadata",
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Current Qdrant chunk count",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Optional retention deadline",
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Latest successful source synchronization",
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
        sa.ForeignKeyConstraint(
            ["collection_id"], ["knowledge_collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection_id",
            "source",
            name="uq_knowledge_sources_collection_source",
        ),
    )
    op.create_index(
        "ix_knowledge_sources_collection_id", "knowledge_sources", ["collection_id"]
    )
    op.create_index(
        "ix_knowledge_sources_expires_at", "knowledge_sources", ["expires_at"]
    )
    op.create_index(
        "ix_knowledge_sources_last_synced_at",
        "knowledge_sources",
        ["last_synced_at"],
    )
    op.create_index("ix_knowledge_sources_owner_id", "knowledge_sources", ["owner_id"])


def downgrade() -> None:
    """Drop tenant knowledge registries."""
    op.drop_index("ix_knowledge_sources_owner_id", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_last_synced_at", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_expires_at", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_collection_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
    op.drop_index(
        "ix_knowledge_collections_owner_id", table_name="knowledge_collections"
    )
    op.drop_index(
        "ix_knowledge_collections_last_synced_at",
        table_name="knowledge_collections",
    )
    op.drop_table("knowledge_collections")
