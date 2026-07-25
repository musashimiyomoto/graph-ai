"""Email account model."""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class EmailAccount(BaseWithID):
    """Reusable user-owned IMAP/SMTP credentials for email nodes."""

    __tablename__ = "email_accounts"

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
        String(128), nullable=False, comment="Account display name"
    )
    email_address: Mapped[str] = mapped_column(
        String(320), nullable=False, comment="Sender email address"
    )
    username: Mapped[str] = mapped_column(
        String(320), nullable=False, comment="IMAP/SMTP login username"
    )
    imap_host: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="IMAP server hostname"
    )
    imap_port: Mapped[int] = mapped_column(
        Integer, default=993, server_default="993", nullable=False
    )
    imap_use_ssl: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    smtp_host: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="SMTP server hostname"
    )
    smtp_port: Mapped[int] = mapped_column(
        Integer, default=587, server_default="587", nullable=False
    )
    smtp_use_tls: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    smtp_use_ssl: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    last_uid: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
        comment="Highest IMAP UID processed so far",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="Whether IMAP polling is active",
    )
