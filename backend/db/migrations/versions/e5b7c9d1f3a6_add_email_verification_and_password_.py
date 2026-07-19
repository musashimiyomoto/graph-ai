"""Add email verification and password recovery state.

Revision ID: e5b7c9d1f3a6
Revises: e2a4c6f8b1d3
Create Date: 2026-07-19 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b7c9d1f3a6"
down_revision: str | None = "e2a4c6f8b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add verified-email state and one-time account action tokens."""
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Time ownership of the email address was verified",
        ),
    )
    # Accounts created before verification existed remain usable.
    op.execute("UPDATE users SET email_verified_at = now()")

    op.create_table(
        "auth_action_tokens",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
            comment="User receiving the account action",
        ),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            comment="Account action permitted by the token",
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 hash of the opaque token",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Time after which the token is invalid",
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Time the one-time token was consumed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Created at",
        ),
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="ID",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_action_tokens_user_id"),
        "auth_action_tokens",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_auth_action_tokens_purpose"),
        "auth_action_tokens",
        ["purpose"],
    )
    op.create_index(
        op.f("ix_auth_action_tokens_token_hash"),
        "auth_action_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Remove account action tokens and verified-email state."""
    op.drop_index(
        op.f("ix_auth_action_tokens_token_hash"),
        table_name="auth_action_tokens",
    )
    op.drop_index(
        op.f("ix_auth_action_tokens_purpose"),
        table_name="auth_action_tokens",
    )
    op.drop_index(
        op.f("ix_auth_action_tokens_user_id"),
        table_name="auth_action_tokens",
    )
    op.drop_table("auth_action_tokens")
    op.drop_column("users", "email_verified_at")
