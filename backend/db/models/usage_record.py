"""Per-tenant usage record model."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class UsageRecord(BaseWithID):
    """A user's consumption within one usage window (a calendar day).

    The durable source of truth for cost/quota reporting: the Redis counter
    used for the fast pre-check on ``POST /executions`` can be lost or reset,
    but this row is authoritative. Exactly one row per ``(user_id,
    period_start)`` — upserted as executions finalize.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_start", name="uq_usage_records_user_period"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="First day of the usage window (UTC calendar day)",
    )
    executions_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
        comment="Executions finalized in this window",
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
        comment="LLM tokens consumed in this window",
    )
