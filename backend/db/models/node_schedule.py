"""Node schedule model."""

from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class NodeSchedule(BaseWithID):
    """Cron schedule state for a Telegram-independent scheduled Input node.

    Kept in its own table rather than inline on `node.data` so the worker's
    `last_fired_at` bump never races the user's own autosave of the node's
    cron expression through the inspector — the two write to different rows.
    """

    __tablename__ = "node_schedules"

    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="The Input node (format=schedule) this schedule drives",
    )
    cron_expression: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Standard 5-field cron expression, evaluated in UTC",
    )
    # Anchor for "is this schedule due": defaults to creation time so a
    # freshly created schedule waits for its first real cron boundary rather
    # than needing None-handling. On each fire the poller resyncs this to the
    # wall-clock check time (not the matched cron boundary) so a worker that
    # was down for several missed boundaries fires exactly once on wake-up
    # and resumes from "now" instead of replaying every boundary it missed.
    last_fired_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        comment="When this schedule last fired, or was created if never fired",
    )
