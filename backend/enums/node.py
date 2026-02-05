"""Node-related enums."""

from enum import StrEnum, auto


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    OUTPUT = auto()


class InputFormat(StrEnum):
    """Input node payload formats."""

    TEXT = auto()


class OutputFormat(StrEnum):
    """Output node payload formats."""

    TEXT = auto()
