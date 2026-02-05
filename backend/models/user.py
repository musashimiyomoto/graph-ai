"""User model."""

from backend.models import BaseWithDate, BaseWithID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class User(BaseWithID, BaseWithDate):
    """Application user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Email address",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password",
    )
