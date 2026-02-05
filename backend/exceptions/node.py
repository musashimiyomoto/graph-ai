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


class NodeTypeMismatchError(BaseError):
    """Raised when a node type does not match the expected type."""

    def __init__(
        self,
        message: str = "Node type mismatch",
        status_code: HTTPStatus = HTTPStatus.CONFLICT,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class NodeConfigExistsError(BaseError):
    """Raised when a node configuration already exists."""

    def __init__(
        self,
        message: str = "Node config already exists",
        status_code: HTTPStatus = HTTPStatus.CONFLICT,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
