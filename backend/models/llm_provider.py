"""LLM provider model."""

from backend.enums import LLMProviderType
from backend.models import BaseWithID
from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class LLMProvider(BaseWithID):
    """LLM provider configuration."""

    __tablename__ = "llm_providers"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner user ID",
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
    api_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted API key",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512),
        comment="Custom base URL for self-hosted providers",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Default provider for user",
    )
