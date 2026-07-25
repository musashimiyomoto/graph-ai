"""Durable state-related enums."""

from enum import StrEnum, auto


class StateScope(StrEnum):
    """Lifetime and identity boundary for one state value."""

    EXECUTION = auto()
    CONVERSATION = auto()
    USER = auto()
    WORKFLOW = auto()


class StateHistoryOperation(StrEnum):
    """Append-only mutation types recorded for state history."""

    CREATE = auto()
    UPDATE = auto()
    DELETE = auto()
