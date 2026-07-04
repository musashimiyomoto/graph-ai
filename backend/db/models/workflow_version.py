"""Workflow version model."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithDate, BaseWithID


class WorkflowVersion(BaseWithID, BaseWithDate):
    """Immutable snapshot of a workflow graph at a point in time.

    An execution is pinned to a version so its run is reproducible even after the
    live graph is edited.
    """

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_number"),
    )

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent workflow ID",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Per-workflow incrementing version number",
    )
    graph: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Snapshot of the graph: {'nodes': [...], 'edges': [...]}",
    )
