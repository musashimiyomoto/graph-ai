"""Workflow model."""

from backend.models import BaseWithDate, BaseWithID
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Workflow(BaseWithID, BaseWithDate):
    """Workflow definition."""

    __tablename__ = "workflows"

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner user ID",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Workflow name",
    )
