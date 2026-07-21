"""Edge model."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID


class Edge(BaseWithID):
    """Directed edge between workflow nodes."""

    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "source_node_id",
            "target_node_id",
            name="uq_edges_workflow_source_target",
        ),
    )

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
    source_handle: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Named output handle on the source node (None = default handle)",
    )
    coercion: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Explicit typed-value conversion applied while traversing the edge",
    )
