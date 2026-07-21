"""Add universal trigger event envelopes.

Revision ID: e5c7a9b1d3f6
Revises: d4a6c8e0f2b1
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5c7a9b1d3f6"
down_revision: str | None = "d4a6c8e0f2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist normalized trigger envelopes and their idempotency key."""
    op.add_column(
        "executions",
        sa.Column(
            "trigger_event",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Versioned provider-neutral event that triggered this execution",
        ),
    )
    op.add_column(
        "executions",
        sa.Column(
            "trigger_external_id",
            sa.String(length=255),
            nullable=True,
            comment="Denormalized external trigger ID used for idempotency",
        ),
    )
    op.execute(
        """
        UPDATE executions
        SET trigger_event = jsonb_build_object(
            'schema_version', 1,
            'channel', lower(source::text),
            'external_event_id', NULL,
            'sender', CASE
                WHEN email_reply_to IS NULL THEN NULL
                ELSE jsonb_build_object(
                    'id', email_reply_to,
                    'display_name', NULL,
                    'address', email_reply_to
                )
            END,
            'conversation', CASE
                WHEN telegram_chat_id IS NULL THEN NULL
                ELSE jsonb_build_object(
                    'id', telegram_chat_id::text,
                    'thread_id', NULL
                )
            END,
            'locale', NULL,
            'message', jsonb_build_object(
                'kind', 'text',
                'value', coalesce(input_data->>'value', ''),
                'artifact', NULL,
                'metadata', '{}'::jsonb
            ),
            'attachments', '[]'::jsonb,
            'occurred_at', to_jsonb(started_at),
            'metadata', CASE
                WHEN email_subject IS NULL THEN '{}'::jsonb
                ELSE jsonb_build_object('subject', email_subject)
            END,
            'raw_retention', 'discard'
        )
        """
    )
    op.alter_column("executions", "trigger_event", nullable=False)
    op.create_index(
        "uq_executions_trigger_external_event",
        "executions",
        ["workflow_id", "source", "trigger_external_id"],
        unique=True,
        postgresql_where=sa.text("trigger_external_id IS NOT NULL"),
    )
    op.drop_column("executions", "email_subject")
    op.drop_column("executions", "email_reply_to")
    op.drop_column("executions", "telegram_chat_id")


def downgrade() -> None:
    """Remove universal trigger event persistence."""
    op.add_column(
        "executions",
        sa.Column(
            "telegram_chat_id",
            sa.BigInteger(),
            nullable=True,
            comment="Telegram chat to reply to, if this run was triggered by a message",
        ),
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
    op.execute(
        """
        UPDATE executions
        SET telegram_chat_id = CASE
                WHEN lower(source::text) = 'telegram'
                THEN (trigger_event #>> '{conversation,id}')::bigint
                ELSE NULL
            END,
            email_reply_to = CASE
                WHEN lower(source::text) = 'email'
                THEN coalesce(
                    trigger_event #>> '{sender,address}',
                    trigger_event #>> '{sender,id}'
                )
                ELSE NULL
            END,
            email_subject = CASE
                WHEN lower(source::text) = 'email'
                THEN trigger_event #>> '{metadata,subject}'
                ELSE NULL
            END
        """
    )
    op.drop_index("uq_executions_trigger_external_event", table_name="executions")
    op.drop_column("executions", "trigger_external_id")
    op.drop_column("executions", "trigger_event")
