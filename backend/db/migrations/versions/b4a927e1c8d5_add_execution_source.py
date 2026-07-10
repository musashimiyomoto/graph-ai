"""Add execution source.

Revision ID: b4a927e1c8d5
Revises: f171aa16e4f5
Create Date: 2026-07-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4a927e1c8d5"
down_revision: str | None = "f171aa16e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        "executions",
        sa.Column(
            "source",
            sa.Enum("MANUAL", "TELEGRAM", name="executionsource"),
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
    sa.Enum(name="executionsource").drop(op.get_bind(), checkfirst=True)
