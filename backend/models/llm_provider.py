"""LLM provider model."""

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enums import LLMProviderType
from models import BaseWithID


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
