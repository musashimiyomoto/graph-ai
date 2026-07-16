"""Quota exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class QuotaExceededError(BaseError):
    """Raised when a tenant exceeds a usage quota for the current window."""

    def __init__(
        self,
        message: str = "Usage quota exceeded. Please try again later.",
        status_code: HTTPStatus = HTTPStatus.TOO_MANY_REQUESTS,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
