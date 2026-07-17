"""Add email channel accounts and execution reply metadata.

Revision ID: e9a1c4d7b2f6
Revises: d7dc4089af97
Create Date: 2026-07-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9a1c4d7b2f6"
down_revision: str | None = "d7dc4089af97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.execute("ALTER TYPE executionsource ADD VALUE IF NOT EXISTS 'EMAIL'")
    op.execute(
        "COMMENT ON COLUMN executions.source IS "
        "'Channel or mechanism that triggered this execution'"
    )
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="Account display name",
        ),
        sa.Column(
            "email_address",
            sa.String(length=320),
            nullable=False,
            comment="Sender email address",
        ),
        sa.Column(
            "username",
            sa.String(length=320),
            nullable=False,
            comment="IMAP/SMTP login username",
        ),
        sa.Column(
            "password",
            sa.Text(),
            nullable=False,
            comment="Encrypted IMAP/SMTP password",
        ),
        sa.Column(
            "imap_host",
            sa.String(length=255),
            nullable=False,
            comment="IMAP server hostname",
        ),
        sa.Column("imap_port", sa.Integer(), server_default="993", nullable=False),
        sa.Column("imap_use_ssl", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "smtp_host",
            sa.String(length=255),
            nullable=False,
            comment="SMTP server hostname",
        ),
        sa.Column("smtp_port", sa.Integer(), server_default="587", nullable=False),
        sa.Column("smtp_use_tls", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("smtp_use_ssl", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "last_uid",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Highest IMAP UID processed so far",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
            comment="Whether IMAP polling is active",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_accounts_user_id"),
        "email_accounts",
        ["user_id"],
        unique=False,
    )
    op.add_column(
        "executions",
        sa.Column(
            "email_reply_to",
            sa.String(length=320),
            nullable=True,
            comment="Sender address to reply to for email-triggered runs",
        ),
    )
    op.add_column(
        "executions",
        sa.Column(
            "email_subject",
            sa.String(length=998),
            nullable=True,
            comment="Subject of the email that triggered this run",
        ),
    )


def downgrade() -> None:
    """Downgrade database schema.

    PostgreSQL enum values are intentionally retained because removing one
    requires recreating the enum type and every dependent column.
    """
    op.execute(
        "COMMENT ON COLUMN executions.source IS "
        "'What triggered this execution (manual test run vs Telegram traffic)'"
    )
    op.drop_column("executions", "email_subject")
    op.drop_column("executions", "email_reply_to")
    op.drop_index(op.f("ix_email_accounts_user_id"), table_name="email_accounts")
    op.drop_table("email_accounts")
