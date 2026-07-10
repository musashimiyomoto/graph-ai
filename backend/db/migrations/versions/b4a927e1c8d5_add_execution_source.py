"""Add execution source.

Revision ID: b4a927e1c8d5
Revises: f171aa16e4f5
Create Date: 2026-07-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4a927e1c8d5"
down_revision: str | None = "f171aa16e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_execution_source_enum = postgresql.ENUM("MANUAL", "TELEGRAM", name="executionsource")


def upgrade() -> None:
    """Upgrade database schema."""
    # Unlike create_table, add_column does not implicitly CREATE TYPE for a
    # new enum, so it must be created explicitly first.
    _execution_source_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "executions",
        sa.Column(
            "source",
            postgresql.ENUM(
                "MANUAL", "TELEGRAM", name="executionsource", create_type=False
            ),
            nullable=False,
            server_default="MANUAL",
            comment=(
                "What triggered this execution (manual test run vs Telegram traffic)"
            ),
        ),
    )
    # Backfill: a non-null telegram_chat_id was only ever set by the Telegram
    # poller for a message-triggered run (see worker._trigger_executions), so
    # it reliably identifies pre-existing Telegram-sourced executions.
    op.execute(
        "UPDATE executions SET source = 'TELEGRAM' WHERE telegram_chat_id IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column("executions", "source")
    _execution_source_enum.drop(op.get_bind(), checkfirst=True)
