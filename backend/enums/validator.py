"""Validator-related enums."""

from enum import StrEnum, auto


class ValidatorType(StrEnum):
    """Supported validator types for node data fields."""

    MIN_LENGTH = auto()
    SELECT = auto()
    GE = auto()
    LE = auto()
