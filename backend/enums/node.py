"""Node-related enums."""

from enum import StrEnum, auto


class NodeType(StrEnum):
    """Supported node types in a workflow graph."""

    INPUT = auto()
    LLM = auto()
    OUTPUT = auto()
