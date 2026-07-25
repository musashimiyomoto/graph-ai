"""Add durable conversations and typed scoped state.

Revision ID: f8d1b3c5e7a9
Revises: e5c7a9b1d3f6
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8d1b3c5e7a9"
down_revision: str | None = "e5c7a9b1d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

state_scope = postgresql.ENUM(
    "EXECUTION",
    "CONVERSATION",
    "USER",
    "WORKFLOW",
    name="statescope",
    create_type=False,
)
execution_source = postgresql.ENUM(
    "MANUAL",
    "TELEGRAM",
    "SCHEDULE",
    "EMAIL",
    "WEBHOOK",
    "WEB_CHAT",
    name="executionsource",
    create_type=False,
)


def upgrade() -> None:
    """Create conversation, state, and state-history persistence."""
    state_scope.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "conversations",
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Tenant owner ID"),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            nullable=False,
            comment="Workflow receiving this conversation",
        ),
        sa.Column(
            "channel",
            execution_source,
            nullable=False,
            comment="Channel that owns the external thread identity",
        ),
        sa.Column(
            "external_thread",
            sa.String(length=32),
            nullable=False,
            comment="MD5 identity key for provider conversation and nested thread",
        ),
        sa.Column(
            "external_conversation_id",
            sa.String(length=998),
            nullable=False,
            comment="Provider conversation identifier",
        ),
        sa.Column(
            "external_thread_id",
            sa.String(length=998),
            nullable=True,
            comment="Optional nested provider thread identifier",
        ),
        sa.Column(
            "public_id",
            sa.String(length=64),
            nullable=False,
            comment="Opaque bearer-safe session identifier",
        ),
        sa.Column(
            "actor_id",
            sa.String(length=320),
            nullable=True,
            comment="Latest normalized sender ID",
        ),
        sa.Column(
            "actor_display_name",
            sa.String(length=320),
            nullable=True,
            comment="Latest normalized sender display name",
        ),
        sa.Column(
            "actor_address",
            sa.String(length=998),
            nullable=True,
            comment="Latest normalized sender address",
        ),
        sa.Column(
            "locale",
            sa.String(length=35),
            nullable=True,
            comment="Latest sender locale",
        ),
        sa.Column(
            "last_event_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Latest event observed for this conversation",
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
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "workflow_id",
            "channel",
            "external_thread",
            name="uq_conversations_workflow_channel_thread",
        ),
    )
    op.create_index(
        "ix_conversations_last_event_at", "conversations", ["last_event_at"]
    )
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    op.create_index("ix_conversations_workflow_id", "conversations", ["workflow_id"])

    op.add_column(
        "executions",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=True,
            comment="Durable normalized conversation for this run",
        ),
    )
    op.create_foreign_key(
        "fk_executions_conversation_id_conversations",
        "executions",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_executions_conversation_id", "executions", ["conversation_id"])

    op.execute(
        """
        INSERT INTO conversations (
            owner_id,
            workflow_id,
            channel,
            external_thread,
            external_conversation_id,
            external_thread_id,
            public_id,
            actor_id,
            actor_display_name,
            actor_address,
            locale,
            last_event_at,
            created_at,
            updated_at
        )
        SELECT DISTINCT ON (e.workflow_id, e.source, thread_key)
            w.owner_id,
            e.workflow_id,
            e.source,
            thread_key,
            e.trigger_event #>> '{conversation,id}',
            nullif(e.trigger_event #>> '{conversation,thread_id}', ''),
            md5(random()::text || clock_timestamp()::text || e.id::text),
            e.trigger_event #>> '{sender,id}',
            e.trigger_event #>> '{sender,display_name}',
            e.trigger_event #>> '{sender,address}',
            e.trigger_event ->> 'locale',
            e.started_at,
            e.started_at,
            e.started_at
        FROM executions e
        JOIN workflows w ON w.id = e.workflow_id
        CROSS JOIN LATERAL (
            SELECT md5(
                char_length(e.trigger_event #>> '{conversation,id}')::text
                || ':'
                || (e.trigger_event #>> '{conversation,id}')
                || ':'
                || coalesce(e.trigger_event #>> '{conversation,thread_id}', '')
            ) AS thread_key
        ) identity
        WHERE jsonb_typeof(e.trigger_event -> 'conversation') = 'object'
        ORDER BY e.workflow_id, e.source, thread_key, e.started_at DESC, e.id DESC
        """
    )
    op.execute(
        """
        UPDATE executions e
        SET conversation_id = c.id
        FROM conversations c
        WHERE c.workflow_id = e.workflow_id
          AND c.channel = e.source
          AND c.external_thread = md5(
              char_length(e.trigger_event #>> '{conversation,id}')::text
              || ':'
              || (e.trigger_event #>> '{conversation,id}')
              || ':'
              || coalesce(e.trigger_event #>> '{conversation,thread_id}', '')
          )
          AND jsonb_typeof(e.trigger_event -> 'conversation') = 'object'
        """
    )

    op.create_table(
        "state_entries",
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Tenant owner ID"),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            nullable=False,
            comment="Workflow boundary for every state scope",
        ),
        sa.Column("scope", state_scope, nullable=False, comment="State lifetime scope"),
        sa.Column(
            "scope_ref",
            sa.String(length=512),
            nullable=False,
            comment="Resolved execution/conversation/user ID",
        ),
        sa.Column(
            "key",
            sa.String(length=128),
            nullable=False,
            comment="Application-defined state key",
        ),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Serialized NodeValue envelope",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Monotonic optimistic-concurrency version",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Optional UTC expiry time",
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
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id",
            "scope",
            "scope_ref",
            "key",
            name="uq_state_entries_workflow_scope_ref_key",
        ),
    )
    op.create_index("ix_state_entries_expires_at", "state_entries", ["expires_at"])
    op.create_index("ix_state_entries_owner_id", "state_entries", ["owner_id"])
    op.create_index("ix_state_entries_workflow_id", "state_entries", ["workflow_id"])

    op.create_table(
        "state_entry_history",
        sa.Column(
            "state_entry_id",
            sa.Integer(),
            nullable=True,
            comment="Current row when it still exists",
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Tenant owner ID"),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            nullable=False,
            comment="Workflow boundary at mutation time",
        ),
        sa.Column(
            "execution_id",
            sa.Integer(),
            nullable=True,
            comment="Execution whose context authorized the mutation",
        ),
        sa.Column("scope", state_scope, nullable=False, comment="State lifetime scope"),
        sa.Column(
            "scope_ref",
            sa.String(length=512),
            nullable=False,
            comment="Resolved scope identity",
        ),
        sa.Column("key", sa.String(length=128), nullable=False, comment="State key"),
        sa.Column(
            "operation",
            sa.String(length=16),
            nullable=False,
            comment="create, update, or delete",
        ),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Typed value after mutation, or deleted value",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            comment="State version affected by this mutation",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Expiry configured by this mutation",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Mutation time",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["executions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["state_entry_id"], ["state_entries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_state_entry_history_created_at", "state_entry_history", ["created_at"]
    )
    op.create_index(
        "ix_state_entry_history_execution_id", "state_entry_history", ["execution_id"]
    )
    op.create_index(
        "ix_state_entry_history_owner_id", "state_entry_history", ["owner_id"]
    )
    op.create_index(
        "ix_state_entry_history_state_entry_id",
        "state_entry_history",
        ["state_entry_id"],
    )
    op.create_index(
        "ix_state_entry_history_workflow_id", "state_entry_history", ["workflow_id"]
    )


def downgrade() -> None:
    """Remove durable conversations and typed scoped state."""
    op.drop_index(
        "ix_state_entry_history_workflow_id", table_name="state_entry_history"
    )
    op.drop_index(
        "ix_state_entry_history_state_entry_id", table_name="state_entry_history"
    )
    op.drop_index("ix_state_entry_history_owner_id", table_name="state_entry_history")
    op.drop_index(
        "ix_state_entry_history_execution_id", table_name="state_entry_history"
    )
    op.drop_index("ix_state_entry_history_created_at", table_name="state_entry_history")
    op.drop_table("state_entry_history")
    op.drop_index("ix_state_entries_workflow_id", table_name="state_entries")
    op.drop_index("ix_state_entries_owner_id", table_name="state_entries")
    op.drop_index("ix_state_entries_expires_at", table_name="state_entries")
    op.drop_table("state_entries")
    state_scope.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_executions_conversation_id", table_name="executions")
    op.drop_constraint(
        "fk_executions_conversation_id_conversations",
        "executions",
        type_="foreignkey",
    )
    op.drop_column("executions", "conversation_id")
    op.drop_index("ix_conversations_workflow_id", table_name="conversations")
    op.drop_index("ix_conversations_owner_id", table_name="conversations")
    op.drop_index("ix_conversations_last_event_at", table_name="conversations")
    op.drop_table("conversations")
