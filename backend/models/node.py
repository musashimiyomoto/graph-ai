"""Node models."""

from backend.enums import InputFormat, NodeType, OutputFormat
from backend.models import Base, BaseWithID
from sqlalchemy import Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


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


class InputNode(Base):
    """Input node configuration."""

    __tablename__ = "input_nodes"

    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Parent node ID",
    )

    format: Mapped[InputFormat] = mapped_column(
        Enum(InputFormat),
        default=InputFormat.TEXT,
        comment="Input format type",
    )


class LLMNode(Base):
    """LLM node configuration."""

    __tablename__ = "llm_nodes"

    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Parent node ID",
    )
    llm_provider_id: Mapped[int] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="LLM provider ID",
    )

    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Model identifier (e.g., gpt-4)",
    )
    temperature: Mapped[float] = mapped_column(
        Float,
        default=0.7,
        comment="Sampling temperature (0.0-2.0)",
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=1024,
        comment="Max tokens in response",
    )


class OutputNode(Base):
    """Output node configuration."""

    __tablename__ = "output_nodes"

    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Parent node ID",
    )

    format: Mapped[OutputFormat] = mapped_column(
        Enum(OutputFormat),
        default=OutputFormat.TEXT,
        comment="Output format type",
    )
