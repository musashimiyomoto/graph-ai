"""One-time authentication action token model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import BaseWithID


class AuthActionToken(BaseWithID):
    """Hashed, expiring token for email verification or password reset."""

    __tablename__ = "auth_action_tokens"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User receiving the account action",
    )
    purpose: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Account action permitted by the token",
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of the opaque token",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Time after which the token is invalid",
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Time the one-time token was consumed",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Created at",
    )
