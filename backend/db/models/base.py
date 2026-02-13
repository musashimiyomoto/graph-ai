"""Shared SQLAlchemy declarative base mixins."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base SQLAlchemy model with readable string representations."""

    __abstract__ = True

    def __repr__(self) -> str:
        """Return a compact debug-friendly representation."""
        pk = getattr(self, "id", None)
        return f"<{self.__class__.__name__}(id={pk})>"

    def __str__(self) -> str:
        """Return the same representation as `__repr__`."""
        return self.__repr__()


class BaseWithID(Base):
    """Base model that adds an integer primary key."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="ID")


class BaseWithDate(Base):
    """Base model that adds created/updated timestamps."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="Created at",
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        comment="Updated at",
    )
