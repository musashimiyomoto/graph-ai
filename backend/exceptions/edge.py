"""Edge-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class EdgeNotFoundError(BaseError):
    """Raised when an edge cannot be found."""

    def __init__(
        self,
        message: str = "Edge not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class EdgeNodeMismatchError(BaseError):
    """Raised when a node does not belong to the workflow."""

    def __init__(
        self,
        message: str = "Node does not belong to workflow",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
