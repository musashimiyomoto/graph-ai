"""Durable state exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class StateEntryNotFoundError(BaseError):
    """Raised when a state key is missing or expired."""

    def __init__(
        self,
        message: str = "State entry not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class StateScopeUnavailableError(BaseError):
    """Raised when an execution lacks identity for a requested scope."""

    def __init__(
        self,
        message: str = "State scope is unavailable for this execution",
        status_code: HTTPStatus = HTTPStatus.UNPROCESSABLE_ENTITY,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class StateVersionConflictError(BaseError):
    """Raised when optimistic-concurrency versions do not match."""

    def __init__(
        self,
        message: str = "State entry version does not match",
        status_code: HTTPStatus = HTTPStatus.CONFLICT,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
