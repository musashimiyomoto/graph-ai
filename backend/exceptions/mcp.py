"""MCP server and tool exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class MCPServerNotFoundError(BaseError):
    """Raised when an owned MCP server is not found."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="MCP server not found",
            status_code=HTTPStatus.NOT_FOUND,
        )


class MCPServerAlreadyExistsError(BaseError):
    """Raised when an MCP server name is already used."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="An MCP server with this name already exists",
            status_code=HTTPStatus.CONFLICT,
        )


class MCPConnectionError(BaseError):
    """Raised when discovery or a tool call fails."""

    def __init__(self, message: str = "MCP server request failed") -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=HTTPStatus.BAD_GATEWAY)
