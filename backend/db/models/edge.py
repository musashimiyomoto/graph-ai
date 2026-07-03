"""Edge model."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class Edge(BaseWithID):
    """Directed edge between workflow nodes."""

    __tablename__ = "edges"

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent workflow ID",
    )
    source_node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source node ID",
    )
    target_node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target node ID",
    )
