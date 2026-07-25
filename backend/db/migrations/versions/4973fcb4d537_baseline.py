"""Create the fresh Graph AI database baseline.

Revision ID: 4973fcb4d537
Revises:
Create Date: 2026-07-25 21:18:27.440460

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4973fcb4d537"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:  # noqa: PLR0915
    """Create the current schema directly, without transitional data steps."""
    op.create_table(
        "users",
        sa.Column(
            "email", sa.String(length=255), nullable=False, comment="Email address"
        ),
        sa.Column(
            "hashed_password",
            sa.String(length=255),
            nullable=False,
            comment="Hashed password",
        ),
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Time ownership of the email address was verified",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
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
    op.create_index(
        op.f("ix_artifacts_checksum"), "artifacts", ["checksum"], unique=False
    )
    op.create_index(
        "ix_artifacts_expires_at", "artifacts", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_artifacts_user_id"), "artifacts", ["user_id"], unique=False
    )
    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Acting user ID"),
        sa.Column(
            "action",
            sa.String(length=64),
            nullable=False,
            comment="Action name, e.g. 'execution.create' or 'workflow.delete'",
        ),
        sa.Column(
            "entity_type",
            sa.String(length=64),
            nullable=False,
            comment="Affected entity type, e.g. 'execution', 'workflow'",
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=True,
            comment="Affected entity ID, if the action targets a specific row",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extra structured context for the action",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the action occurred",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False
    )
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
            server_default=sa.text("now()"),
            nullable=False,
            comment="Created at",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_action_tokens_purpose"),
        "auth_action_tokens",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_action_tokens_token_hash"),
        "auth_action_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_auth_action_tokens_user_id"),
        "auth_action_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
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
    )
    op.create_index(
        op.f("ix_auth_sessions_token_hash"),
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False
    )
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
            sa.Enum("NONE", "API_KEY", "OAUTH2", name="connectionauthtype"),
            nullable=False,
            comment="Credential protocol",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "ACTIVE", "UNHEALTHY", "REVOKED", name="connectionstatus"
            ),
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
        sa.UniqueConstraint(
            "user_id", "provider", "name", name="uq_connections_user_provider_name"
        ),
    )
    op.create_index(
        op.f("ix_connections_last_used_at"),
        "connections",
        ["last_used_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connections_provider"), "connections", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_connections_revoked_at"), "connections", ["revoked_at"], unique=False
    )
    op.create_index(
        op.f("ix_connections_user_id"), "connections", ["user_id"], unique=False
    )
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
        sa.UniqueConstraint(
            "owner_id", "name", name="uq_knowledge_collections_owner_name"
        ),
        sa.UniqueConstraint("physical_name"),
    )
    op.create_index(
        op.f("ix_knowledge_collections_last_synced_at"),
        "knowledge_collections",
        ["last_synced_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_collections_owner_id"),
        "knowledge_collections",
        ["owner_id"],
        unique=False,
    )
    op.create_table(
        "usage_records",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "period_start",
            sa.Date(),
            nullable=False,
            comment="First day of the usage window (UTC calendar day)",
        ),
        sa.Column(
            "executions_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Executions finalized in this window",
        ),
        sa.Column(
            "total_tokens",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="LLM tokens consumed in this window",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "period_start", name="uq_usage_records_user_period"
        ),
    )
    op.create_index(
        op.f("ix_usage_records_user_id"), "usage_records", ["user_id"], unique=False
    )
    op.create_table(
        "workflows",
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "name", sa.String(length=255), nullable=False, comment="Workflow name"
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
    )
    op.create_index(
        op.f("ix_workflows_owner_id"), "workflows", ["owner_id"], unique=False
    )
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="State creation time",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index(
        op.f("ix_connection_oauth_states_connection_id"),
        "connection_oauth_states",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connection_oauth_states_expires_at"),
        "connection_oauth_states",
        ["expires_at"],
        unique=False,
    )
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
            sa.Enum(
                "MANUAL",
                "TELEGRAM",
                "SCHEDULE",
                "EMAIL",
                "WEBHOOK",
                "WEB_CHAT",
                name="executionsource",
            ),
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
        op.f("ix_conversations_last_event_at"),
        "conversations",
        ["last_event_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_owner_id"), "conversations", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_conversations_workflow_id"),
        "conversations",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "email_accounts",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Unified credential connection ID",
        ),
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
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
    )
    op.create_index(
        op.f("ix_email_accounts_user_id"), "email_accounts", ["user_id"], unique=False
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
            "collection_id", "source", name="uq_knowledge_sources_collection_source"
        ),
    )
    op.create_index(
        op.f("ix_knowledge_sources_collection_id"),
        "knowledge_sources",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_sources_expires_at"),
        "knowledge_sources",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_sources_last_synced_at"),
        "knowledge_sources",
        ["last_synced_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_sources_owner_id"),
        "knowledge_sources",
        ["owner_id"],
        unique=False,
    )
    op.create_table(
        "llm_providers",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Unified credential connection ID",
        ),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="Provider display name",
        ),
        sa.Column(
            "type",
            sa.Enum("OLLAMA", "OPENAI", "ANTHROPIC", name="llmprovidertype"),
            nullable=False,
            comment="Provider type",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Provider configuration",
        ),
        sa.Column(
            "base_url",
            sa.String(length=512),
            nullable=False,
            comment="Custom base URL for self-hosted providers",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_llm_providers_user_name"),
    )
    op.create_index(
        op.f("ix_llm_providers_user_id"), "llm_providers", ["user_id"], unique=False
    )
    op.create_table(
        "mcp_servers",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Unified credential connection ID",
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_mcp_servers_user_name"),
    )
    op.create_index(
        op.f("ix_mcp_servers_user_id"), "mcp_servers", ["user_id"], unique=False
    )
    op.create_table(
        "nodes",
        sa.Column(
            "workflow_id", sa.Integer(), nullable=False, comment="Parent workflow ID"
        ),
        sa.Column(
            "parent_node_id",
            sa.Integer(),
            nullable=True,
            comment="Owning Loop node's id, or NULL for a top-level graph node",
        ),
        sa.Column(
            "type",
            sa.Enum(
                "INPUT",
                "LLM",
                "TRANSLATE",
                "DELAY",
                "WEB_SEARCH",
                "TEMPLATE",
                "HTTP_REQUEST",
                "CONDITION",
                "SWITCH",
                "MCP_TOOL",
                "CODE_TRANSFORM",
                "VECTOR_INGEST",
                "VECTOR_SEARCH",
                "TABLE",
                "CALL_WORKFLOW",
                "APPROVAL",
                "LOOP",
                "LOOP_INPUT",
                "LOOP_OUTPUT",
                "OUTPUT",
                name="nodetype",
            ),
            nullable=False,
            comment="Node type",
        ),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Node configuration data",
        ),
        sa.Column(
            "position_x", sa.Float(), nullable=False, comment="X position on canvas"
        ),
        sa.Column(
            "position_y", sa.Float(), nullable=False, comment="Y position on canvas"
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["parent_node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_nodes_parent_node_id"), "nodes", ["parent_node_id"], unique=False
    )
    op.create_index(
        op.f("ix_nodes_workflow_id"), "nodes", ["workflow_id"], unique=False
    )
    op.create_table(
        "postgres_connections",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Unified credential connection ID",
        ),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="Connection display name",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
        sa.UniqueConstraint(
            "user_id", "name", name="uq_postgres_connections_user_name"
        ),
    )
    op.create_index(
        op.f("ix_postgres_connections_user_id"),
        "postgres_connections",
        ["user_id"],
        unique=False,
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
        sa.Column(
            "scope",
            sa.Enum("EXECUTION", "CONVERSATION", "USER", "WORKFLOW", name="statescope"),
            nullable=False,
            comment="State lifetime scope",
        ),
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
    op.create_index(
        op.f("ix_state_entries_expires_at"),
        "state_entries",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_state_entries_owner_id"), "state_entries", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_state_entries_workflow_id"),
        "state_entries",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "telegram_bots",
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Owner user ID"),
        sa.Column(
            "connection_id",
            sa.Integer(),
            nullable=False,
            comment="Unified credential connection ID",
        ),
        sa.Column(
            "name", sa.String(length=128), nullable=False, comment="Bot display name"
        ),
        sa.Column(
            "last_update_id",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Highest Telegram update_id processed so far",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
            comment="Whether polling is active for this bot",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id"),
    )
    op.create_index(
        op.f("ix_telegram_bots_user_id"), "telegram_bots", ["user_id"], unique=False
    )
    op.create_table(
        "workflow_versions",
        sa.Column(
            "workflow_id", sa.Integer(), nullable=False, comment="Parent workflow ID"
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            comment="Per-workflow incrementing version number",
        ),
        sa.Column(
            "graph",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Snapshot of the graph: {'nodes': [...], 'edges': [...]}",
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
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "version", name="uq_workflow_versions_number"
        ),
    )
    op.create_index(
        op.f("ix_workflow_versions_workflow_id"),
        "workflow_versions",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "edges",
        sa.Column(
            "workflow_id", sa.Integer(), nullable=False, comment="Parent workflow ID"
        ),
        sa.Column(
            "source_node_id", sa.Integer(), nullable=False, comment="Source node ID"
        ),
        sa.Column(
            "target_node_id", sa.Integer(), nullable=False, comment="Target node ID"
        ),
        sa.Column(
            "source_handle",
            sa.String(),
            nullable=True,
            comment="Named output handle on the source node (None = default handle)",
        ),
        sa.Column(
            "target_handle",
            sa.String(),
            nullable=True,
            comment="Named input handle on the target node (None = default handle)",
        ),
        sa.Column(
            "coercion",
            sa.String(length=64),
            nullable=True,
            comment="Explicit typed-value conversion applied while traversing the edge",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["source_node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_edges_source_node_id"), "edges", ["source_node_id"], unique=False
    )
    op.create_index(
        op.f("ix_edges_target_node_id"), "edges", ["target_node_id"], unique=False
    )
    op.create_index(
        op.f("ix_edges_workflow_id"), "edges", ["workflow_id"], unique=False
    )
    op.create_index(
        "uq_edges_workflow_source_target_handles",
        "edges",
        [
            "workflow_id",
            "source_node_id",
            "target_node_id",
            sa.literal_column("coalesce(source_handle, '')"),
            sa.literal_column("coalesce(target_handle, '')"),
        ],
        unique=True,
    )
    op.create_table(
        "executions",
        sa.Column(
            "workflow_id", sa.Integer(), nullable=False, comment="Parent workflow ID"
        ),
        sa.Column(
            "version_id",
            sa.Integer(),
            nullable=False,
            comment="Pinned workflow version snapshot",
        ),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=True,
            comment="Durable normalized conversation for this run",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_APPROVAL",
                "WAITING_DELAY",
                "SUCCESS",
                "FAILED",
                "CANCELLED",
                "REJECTED",
                "SKIPPED",
                name="executionstatus",
            ),
            nullable=False,
            comment="Execution status",
        ),
        sa.Column(
            "source",
            sa.Enum(
                "MANUAL",
                "TELEGRAM",
                "SCHEDULE",
                "EMAIL",
                "WEBHOOK",
                "WEB_CHAT",
                name="executionsource",
            ),
            server_default="MANUAL",
            nullable=False,
            comment="Channel or mechanism that triggered this execution",
        ),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Input data for execution",
        ),
        sa.Column(
            "trigger_event",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Versioned provider-neutral event that triggered this execution",
        ),
        sa.Column(
            "trigger_external_id",
            sa.String(length=255),
            nullable=True,
            comment="Denormalized external trigger ID used for idempotency",
        ),
        sa.Column(
            "output_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Output data from execution",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="Error message if failed"),
        sa.Column(
            "approval_node_id",
            sa.Integer(),
            nullable=True,
            comment="Node awaiting an owner approval decision",
        ),
        sa.Column(
            "approval_prompt",
            sa.Text(),
            nullable=True,
            comment="Human-readable approval request",
        ),
        sa.Column(
            "approval_input",
            sa.Text(),
            nullable=True,
            comment="Upstream value awaiting approval",
        ),
        sa.Column(
            "queue_job_id",
            sa.String(length=255),
            nullable=True,
            comment="Current ARQ job ID for cancellation/resume",
        ),
        sa.Column(
            "wait_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Earliest durable Delay checkpoint wake-up time",
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=True,
            comment="Total LLM prompt tokens across the run",
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=True,
            comment="Total LLM completion tokens across the run",
        ),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=True,
            comment="Total LLM tokens across the run",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Execution start time",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Execution end time",
        ),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Last node-completion time, bumped as the run progresses so the "
                "stuck-execution reaper can tell a long-but-active run from one "
                "that's actually stalled"
            ),
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["workflow_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_executions_conversation_id"),
        "executions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_executions_version_id"), "executions", ["version_id"], unique=False
    )
    op.create_index(
        op.f("ix_executions_workflow_id"), "executions", ["workflow_id"], unique=False
    )
    op.create_index(
        "uq_executions_trigger_external_event",
        "executions",
        ["workflow_id", "source", "trigger_external_id"],
        unique=True,
        postgresql_where=sa.text("trigger_external_id IS NOT NULL"),
    )
    op.create_table(
        "node_schedules",
        sa.Column(
            "node_id",
            sa.Integer(),
            nullable=False,
            comment="The Input node (format=schedule) this schedule drives",
        ),
        sa.Column(
            "cron_expression",
            sa.Text(),
            nullable=False,
            comment="Standard 5-field cron expression, evaluated in UTC",
        ),
        sa.Column(
            "last_fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this schedule last fired, or was created if never fired",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id"),
    )
    op.create_table(
        "node_executions",
        sa.Column(
            "execution_id", sa.Integer(), nullable=False, comment="Parent execution ID"
        ),
        sa.Column(
            "node_id",
            sa.Integer(),
            nullable=False,
            comment="Executed node ID (not FK-enforced; the node may since be deleted)",
        ),
        sa.Column(
            "node_type",
            sa.Enum(
                "INPUT",
                "LLM",
                "TRANSLATE",
                "DELAY",
                "WEB_SEARCH",
                "TEMPLATE",
                "HTTP_REQUEST",
                "CONDITION",
                "SWITCH",
                "MCP_TOOL",
                "CODE_TRANSFORM",
                "VECTOR_INGEST",
                "VECTOR_SEARCH",
                "TABLE",
                "CALL_WORKFLOW",
                "APPROVAL",
                "LOOP",
                "LOOP_INPUT",
                "LOOP_OUTPUT",
                "OUTPUT",
                name="nodetype",
            ),
            nullable=True,
            comment="Node type at execution time (denormalized snapshot)",
        ),
        sa.Column(
            "node_label",
            sa.Text(),
            nullable=True,
            comment="Node label at execution time (denormalized snapshot)",
        ),
        sa.Column(
            "iteration",
            sa.Integer(),
            nullable=True,
            comment="Loop iteration index (0-based); NULL for a top-level node",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_APPROVAL",
                "WAITING_DELAY",
                "SUCCESS",
                "FAILED",
                "CANCELLED",
                "REJECTED",
                "SKIPPED",
                name="executionstatus",
            ),
            nullable=False,
            comment="Node execution status",
        ),
        sa.Column(
            "output_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Typed NodeValue envelopes keyed by declared output port name",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="Error message if the node failed",
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=True,
            comment="LLM prompt/input tokens, if this node called an LLM",
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=True,
            comment="LLM completion/output tokens, if this node called an LLM",
        ),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=True,
            comment="LLM total tokens, if this node called an LLM",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Node execution start time",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Node execution end time",
        ),
        sa.Column(
            "wait_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Durable Delay checkpoint wake-up time",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_node_executions_execution_id"),
        "node_executions",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_node_executions_node_id"), "node_executions", ["node_id"], unique=False
    )
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
        sa.Column(
            "scope",
            sa.Enum("EXECUTION", "CONVERSATION", "USER", "WORKFLOW", name="statescope"),
            nullable=False,
            comment="State lifetime scope",
        ),
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Mutation time",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="ID"),
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
        op.f("ix_state_entry_history_created_at"),
        "state_entry_history",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_state_entry_history_execution_id"),
        "state_entry_history",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_state_entry_history_owner_id"),
        "state_entry_history",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_state_entry_history_state_entry_id"),
        "state_entry_history",
        ["state_entry_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_state_entry_history_workflow_id"),
        "state_entry_history",
        ["workflow_id"],
        unique=False,
    )


def downgrade() -> None:  # noqa: PLR0915
    """Remove the fresh baseline schema."""
    op.drop_index(
        op.f("ix_state_entry_history_workflow_id"), table_name="state_entry_history"
    )
    op.drop_index(
        op.f("ix_state_entry_history_state_entry_id"), table_name="state_entry_history"
    )
    op.drop_index(
        op.f("ix_state_entry_history_owner_id"), table_name="state_entry_history"
    )
    op.drop_index(
        op.f("ix_state_entry_history_execution_id"), table_name="state_entry_history"
    )
    op.drop_index(
        op.f("ix_state_entry_history_created_at"), table_name="state_entry_history"
    )
    op.drop_table("state_entry_history")
    op.drop_index(op.f("ix_node_executions_node_id"), table_name="node_executions")
    op.drop_index(op.f("ix_node_executions_execution_id"), table_name="node_executions")
    op.drop_table("node_executions")
    op.drop_table("node_schedules")
    op.drop_index(
        "uq_executions_trigger_external_event",
        table_name="executions",
        postgresql_where=sa.text("trigger_external_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_executions_workflow_id"), table_name="executions")
    op.drop_index(op.f("ix_executions_version_id"), table_name="executions")
    op.drop_index(op.f("ix_executions_conversation_id"), table_name="executions")
    op.drop_table("executions")
    op.drop_index("uq_edges_workflow_source_target_handles", table_name="edges")
    op.drop_index(op.f("ix_edges_workflow_id"), table_name="edges")
    op.drop_index(op.f("ix_edges_target_node_id"), table_name="edges")
    op.drop_index(op.f("ix_edges_source_node_id"), table_name="edges")
    op.drop_table("edges")
    op.drop_index(
        op.f("ix_workflow_versions_workflow_id"), table_name="workflow_versions"
    )
    op.drop_table("workflow_versions")
    op.drop_index(op.f("ix_telegram_bots_user_id"), table_name="telegram_bots")
    op.drop_table("telegram_bots")
    op.drop_index(op.f("ix_state_entries_workflow_id"), table_name="state_entries")
    op.drop_index(op.f("ix_state_entries_owner_id"), table_name="state_entries")
    op.drop_index(op.f("ix_state_entries_expires_at"), table_name="state_entries")
    op.drop_table("state_entries")
    op.drop_index(
        op.f("ix_postgres_connections_user_id"), table_name="postgres_connections"
    )
    op.drop_table("postgres_connections")
    op.drop_index(op.f("ix_nodes_workflow_id"), table_name="nodes")
    op.drop_index(op.f("ix_nodes_parent_node_id"), table_name="nodes")
    op.drop_table("nodes")
    op.drop_index(op.f("ix_mcp_servers_user_id"), table_name="mcp_servers")
    op.drop_table("mcp_servers")
    op.drop_index(op.f("ix_llm_providers_user_id"), table_name="llm_providers")
    op.drop_table("llm_providers")
    op.drop_index(op.f("ix_knowledge_sources_owner_id"), table_name="knowledge_sources")
    op.drop_index(
        op.f("ix_knowledge_sources_last_synced_at"), table_name="knowledge_sources"
    )
    op.drop_index(
        op.f("ix_knowledge_sources_expires_at"), table_name="knowledge_sources"
    )
    op.drop_index(
        op.f("ix_knowledge_sources_collection_id"), table_name="knowledge_sources"
    )
    op.drop_table("knowledge_sources")
    op.drop_index(op.f("ix_email_accounts_user_id"), table_name="email_accounts")
    op.drop_table("email_accounts")
    op.drop_index(op.f("ix_conversations_workflow_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_owner_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_last_event_at"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(
        op.f("ix_connection_oauth_states_expires_at"),
        table_name="connection_oauth_states",
    )
    op.drop_index(
        op.f("ix_connection_oauth_states_connection_id"),
        table_name="connection_oauth_states",
    )
    op.drop_table("connection_oauth_states")
    op.drop_index(op.f("ix_workflows_owner_id"), table_name="workflows")
    op.drop_table("workflows")
    op.drop_index(op.f("ix_usage_records_user_id"), table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index(
        op.f("ix_knowledge_collections_owner_id"), table_name="knowledge_collections"
    )
    op.drop_index(
        op.f("ix_knowledge_collections_last_synced_at"),
        table_name="knowledge_collections",
    )
    op.drop_table("knowledge_collections")
    op.drop_index(op.f("ix_connections_user_id"), table_name="connections")
    op.drop_index(op.f("ix_connections_revoked_at"), table_name="connections")
    op.drop_index(op.f("ix_connections_provider"), table_name="connections")
    op.drop_index(op.f("ix_connections_last_used_at"), table_name="connections")
    op.drop_table("connections")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_token_hash"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        op.f("ix_auth_action_tokens_user_id"), table_name="auth_action_tokens"
    )
    op.drop_index(
        op.f("ix_auth_action_tokens_token_hash"), table_name="auth_action_tokens"
    )
    op.drop_index(
        op.f("ix_auth_action_tokens_purpose"), table_name="auth_action_tokens"
    )
    op.drop_table("auth_action_tokens")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_artifacts_user_id"), table_name="artifacts")
    op.drop_index("ix_artifacts_expires_at", table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_checksum"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_table("users")
    op.execute("DROP TYPE statescope")
    op.execute("DROP TYPE nodetype")
    op.execute("DROP TYPE executionstatus")
    op.execute("DROP TYPE executionsource")
    op.execute("DROP TYPE llmprovidertype")
    op.execute("DROP TYPE connectionstatus")
    op.execute("DROP TYPE connectionauthtype")
