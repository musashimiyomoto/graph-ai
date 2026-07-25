"""Unified encrypted connection models."""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithDate, BaseWithID
from enums import ConnectionAuthType, ConnectionStatus


class Connection(BaseWithID, BaseWithDate):
    """One reusable tenant-owned API-key or OAuth connection."""

    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_connections_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Connection display name"
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Adapter/provider key"
    )
    auth_type: Mapped[ConnectionAuthType] = mapped_column(
        Enum(ConnectionAuthType), nullable=False, comment="Credential protocol"
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus), nullable=False, comment="Lifecycle and health status"
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="Non-secret provider and protocol configuration",
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="Granted or requested permission scopes",
    )
    credentials: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted JSON credential/token envelope",
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        comment="OAuth access-token expiry time"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        index=True, comment="Last successful credential use"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        comment="Last health-check completion time"
    )
    last_error: Mapped[str | None] = mapped_column(
        String(1000), comment="Latest bounded health or OAuth error"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        index=True, comment="Time credentials were revoked locally"
    )


class ConnectionOAuthState(BaseWithID):
    """Single-use short-lived OAuth authorization state and PKCE verifier."""

    __tablename__ = "connection_oauth_states"

    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Connection being authorized",
    )
    state_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 of the bearer state returned to the provider",
    )
    code_verifier: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Encrypted OAuth PKCE code verifier"
    )
    redirect_uri: Mapped[str] = mapped_column(
        String(2048), nullable=False, comment="Redirect URI bound to this flow"
    )
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False, index=True, comment="State expiration time"
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, comment="State creation time"
    )
