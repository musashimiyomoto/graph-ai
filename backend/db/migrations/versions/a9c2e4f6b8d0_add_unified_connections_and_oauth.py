"""Add unified encrypted connections and OAuth state.

Revision ID: a9c2e4f6b8d0
Revises: f8d1b3c5e7a9
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c2e4f6b8d0"
down_revision: str | None = "f8d1b3c5e7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

connection_auth_type = postgresql.ENUM(
    "API_KEY",
    "OAUTH2",
    name="connectionauthtype",
    create_type=False,
)
connection_status = postgresql.ENUM(
    "PENDING",
    "ACTIVE",
    "UNHEALTHY",
    "REVOKED",
    name="connectionstatus",
    create_type=False,
)


def upgrade() -> None:
    """Create unified connection metadata, secrets, and OAuth state tables."""
    connection_auth_type.create(op.get_bind(), checkfirst=True)
    connection_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "connections",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="Connection display name",
        ),
        sa.Column(
            "provider",
            sa.String(length=64),
            nullable=False,
            comment="Adapter/provider key",
        ),
        sa.Column(
            "auth_type",
            connection_auth_type,
            nullable=False,
            comment="Credential protocol",
        ),
        sa.Column(
            "status",
            connection_status,
            nullable=False,
            comment="Lifecycle and health status",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Non-secret provider and protocol configuration",
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
            comment="Granted or requested permission scopes",
        ),
        sa.Column(
            "credentials",
            sa.Text(),
            nullable=False,
            comment="Encrypted JSON credential/token envelope",
        ),
        sa.Column(
            "token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="OAuth access-token expiry time",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful credential use",
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last health-check completion time",
        ),
        sa.Column(
            "last_error",
            sa.String(length=1000),
            nullable=True,
            comment="Latest bounded health or OAuth error",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Time credentials were revoked locally",
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
        sa.UniqueConstraint("user_id", "name", name="uq_connections_user_name"),
    )
    op.create_index("ix_connections_last_used_at", "connections", ["last_used_at"])
    op.create_index("ix_connections_provider", "connections", ["provider"])
    op.create_index("ix_connections_revoked_at", "connections", ["revoked_at"])
    op.create_index("ix_connections_user_id", "connections", ["user_id"])

    op.create_table(
        "connection_oauth_states",
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Connection being authorized",
        ),
        sa.Column(
            "state_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 of the bearer state returned to the provider",
        ),
        sa.Column(
            "code_verifier",
            sa.Text(),
            nullable=False,
            comment="Encrypted OAuth PKCE code verifier",
        ),
        sa.Column(
            "redirect_uri",
            sa.String(length=2048),
            nullable=False,
            comment="Redirect URI bound to this flow",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="State expiration time",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="State creation time",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index(
        "ix_connection_oauth_states_connection_id",
        "connection_oauth_states",
        ["connection_id"],
    )
    op.create_index(
        "ix_connection_oauth_states_expires_at",
        "connection_oauth_states",
        ["expires_at"],
    )


def downgrade() -> None:
    """Remove unified connection and OAuth persistence."""
    op.drop_index(
        "ix_connection_oauth_states_expires_at",
        table_name="connection_oauth_states",
    )
    op.drop_index(
        "ix_connection_oauth_states_connection_id",
        table_name="connection_oauth_states",
    )
    op.drop_table("connection_oauth_states")
    op.drop_index("ix_connections_user_id", table_name="connections")
    op.drop_index("ix_connections_revoked_at", table_name="connections")
    op.drop_index("ix_connections_provider", table_name="connections")
    op.drop_index("ix_connections_last_used_at", table_name="connections")
    op.drop_table("connections")
    connection_status.drop(op.get_bind(), checkfirst=True)
    connection_auth_type.drop(op.get_bind(), checkfirst=True)
