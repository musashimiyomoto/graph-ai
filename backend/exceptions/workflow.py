"""Workflow-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class WorkflowNotFoundError(BaseError):
    """Raised when a workflow cannot be found."""

    def __init__(
        self,
        message: str = "Workflow not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
