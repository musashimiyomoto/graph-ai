"""Unified connection-related enums."""

from enum import StrEnum, auto


class ConnectionAuthType(StrEnum):
    """Credential protocol used by a reusable connection."""

    NONE = auto()
    API_KEY = auto()
    OAUTH2 = auto()


class ConnectionStatus(StrEnum):
    """Current lifecycle and health state of a connection."""

    PENDING = auto()
    ACTIVE = auto()
    UNHEALTHY = auto()
    REVOKED = auto()
