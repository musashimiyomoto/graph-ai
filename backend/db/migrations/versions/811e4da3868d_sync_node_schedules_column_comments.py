"""Sync node_schedules column comments.

The node_schedules create_table migration (7e59dce05344) never set the
``comment=`` DDL that the ``NodeSchedule`` model's columns declare, so
`alembic check` flags perpetual drift between the model and the live
schema — same class of gap `4c8b6d2a9f17` fixed for other tables. This
migration brings the DB comments in line with the model without changing
any types/nullability/defaults.

Revision ID: 811e4da3868d
Revises: 3d86d4967e16
Create Date: 2026-07-13 09:00:00.000000

"""

from collections.abc import Sequence
from typing import Any, NamedTuple

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "811e4da3868d"
down_revision: str | None = "3d86d4967e16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class _ColumnComment(NamedTuple):
    """A column that's missing its model-declared comment in the live schema."""

    table: str
    column: str
    existing_type: sa.types.TypeEngine
    existing_nullable: bool
    existing_server_default: Any
    comment: str


_COMMENTS: list[_ColumnComment] = [
    _ColumnComment(
        table="node_schedules",
        column="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default=None,
        comment="ID",
    ),
    _ColumnComment(
        table="node_schedules",
        column="node_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_server_default=None,
        comment="The Input node (format=schedule) this schedule drives",
    ),
    _ColumnComment(
        table="node_schedules",
        column="cron_expression",
        existing_type=sa.Text(),
        existing_nullable=False,
        existing_server_default=None,
        comment="Standard 5-field cron expression, evaluated in UTC",
    ),
    _ColumnComment(
        table="node_schedules",
        column="last_fired_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        comment="When this schedule last fired, or was created if never fired",
    ),
]


def upgrade() -> None:
    """Upgrade database schema."""
    for entry in _COMMENTS:
        op.alter_column(
            entry.table,
            entry.column,
            existing_type=entry.existing_type,
            existing_nullable=entry.existing_nullable,
            existing_server_default=entry.existing_server_default,
            comment=entry.comment,
        )


def downgrade() -> None:
    """Downgrade database schema."""
    for entry in _COMMENTS:
        op.alter_column(
            entry.table,
            entry.column,
            existing_type=entry.existing_type,
            existing_nullable=entry.existing_nullable,
            existing_server_default=entry.existing_server_default,
            comment=None,
        )
