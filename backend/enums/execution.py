"""Execution-related enums."""

from enum import StrEnum, auto


class ExecutionStatus(StrEnum):
    """Lifecycle states for workflow executions."""

    CREATED = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


class ExecutionSource(StrEnum):
    """What triggered a workflow execution.

    Separates a workflow owner's own test runs from real end-user traffic, so
    the frontend can show them in distinct views (Test Runs vs Activity Log)
    instead of one merged list.
    """

    MANUAL = auto()
    TELEGRAM = auto()
    SCHEDULE = auto()
