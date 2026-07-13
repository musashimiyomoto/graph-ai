"""Node models."""

from sqlalchemy import Enum, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models import BaseWithID
from enums import NodeType


class Node(BaseWithID):
    """Base node in a workflow graph."""

    __tablename__ = "nodes"

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent workflow ID",
    )
    # NULL for a top-level graph node; the owning Loop node's id for a node
    # inside that loop's body. Self-referential so a loop body is just
    # ordinary nodes/edges scoped by this column, not a separate table —
    # CRUD, the field catalog, and whole-workflow snapshots all keep working
    # unchanged; only graph *validation/execution* needs to partition by it.
    parent_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Owning Loop node's id, or NULL for a top-level graph node",
    )

    type: Mapped[NodeType] = mapped_column(
        Enum(NodeType),
        nullable=False,
        comment="Node type",
    )

    data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="Node configuration data",
    )

    position_x: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="X position on canvas",
    )
    position_y: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="Y position on canvas",
    )
