"""Authentication-related enums."""

from enum import StrEnum


class AuthActionPurpose(StrEnum):
    """Purpose of a one-time account action token."""

    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105
