"""Execution-related enums."""

from enum import StrEnum, auto


class ExecutionStatus(StrEnum):
    """Lifecycle states for workflow executions."""

    CREATED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
