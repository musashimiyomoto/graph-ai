"""Node models."""

from sqlalchemy import Enum, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enums import NodeType
from models import BaseWithID


class Node(BaseWithID):
    """Base node in a workflow graph."""

    __tablename__ = "nodes"

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent workflow ID",
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
