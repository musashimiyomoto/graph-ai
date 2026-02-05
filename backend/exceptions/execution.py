"""Execution-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class ExecutionNotFoundError(BaseError):
    """Raised when an execution cannot be found."""

    def __init__(
        self,
        message: str = "Execution not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
