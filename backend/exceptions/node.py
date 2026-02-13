"""Node-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class NodeNotFoundError(BaseError):
    """Raised when a node cannot be found."""

    def __init__(
        self,
        message: str = "Node not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class NodeDataValidationError(BaseError):
    """Raised when node data fails validation."""

    def __init__(
        self,
        message: str = "Invalid node data",
        status_code: HTTPStatus = HTTPStatus.UNPROCESSABLE_ENTITY,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class WebSearchConnectionError(BaseError):
    """Raised when a web search request fails."""

    def __init__(
        self,
        message: str = "Web search provider request failed",
        status_code: HTTPStatus = HTTPStatus.BAD_GATEWAY,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
