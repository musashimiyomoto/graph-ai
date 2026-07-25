"""Unified connection exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class ConnectionNotFoundError(BaseError):
    """Raised when an owned connection cannot be found."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="Connection not found", status_code=HTTPStatus.NOT_FOUND
        )


class ConnectionAlreadyExistsError(BaseError):
    """Raised when a tenant reuses a connection display name."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="A connection with this name already exists",
            status_code=HTTPStatus.CONFLICT,
        )


class ConnectionRevokedError(BaseError):
    """Raised when revoked credentials are used."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="Connection credentials have been revoked",
            status_code=HTTPStatus.CONFLICT,
        )


class OAuthStateError(BaseError):
    """Raised for invalid, expired, or replayed OAuth state."""

    def __init__(self, message: str = "OAuth state is invalid or expired") -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST)


class OAuthExchangeError(BaseError):
    """Raised when an OAuth provider rejects token exchange or refresh."""

    def __init__(self, message: str = "OAuth token exchange failed") -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=HTTPStatus.BAD_GATEWAY)
