"""LLM provider model."""

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID
from enums import LLMProviderType


class LLMProvider(BaseWithID):
    """LLM provider configuration."""

    __tablename__ = "llm_providers"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_llm_providers_user_name"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Unified credential connection ID",
    )

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Provider display name",
    )
    type: Mapped[LLMProviderType] = mapped_column(
        Enum(LLMProviderType),
        nullable=False,
        comment="Provider type",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="Provider configuration",
    )
    base_url: Mapped[str] = mapped_column(
        String(512),
        comment="Custom base URL for self-hosted providers",
    )
