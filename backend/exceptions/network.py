"""Network-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class BlockedURLError(BaseError):
    """Raised when an outbound URL is blocked by the SSRF guard."""

    def __init__(
        self,
        message: str = "URL is not allowed",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
