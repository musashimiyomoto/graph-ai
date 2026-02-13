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


class ExecutionGraphValidationError(BaseError):
    """Raised when a workflow graph cannot be executed."""

    def __init__(
        self,
        message: str = "Workflow graph is not valid for execution",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class ExecutionInputValidationError(BaseError):
    """Raised when execution input payload is invalid."""

    def __init__(
        self,
        message: str = "Execution input payload is invalid",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
