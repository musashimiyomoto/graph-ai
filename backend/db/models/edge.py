"""Edge model."""

from sqlalchemy import ForeignKey, Index, String, func
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
    source_handle: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Named output handle on the source node (None = default handle)",
    )
    target_handle: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Named input handle on the target node (None = default handle)",
    )
    coercion: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Explicit typed-value conversion applied while traversing the edge",
    )


Index(
    "uq_edges_workflow_source_target_handles",
    Edge.workflow_id,
    Edge.source_node_id,
    Edge.target_node_id,
    func.coalesce(Edge.source_handle, ""),
    func.coalesce(Edge.target_handle, ""),
    unique=True,
)
