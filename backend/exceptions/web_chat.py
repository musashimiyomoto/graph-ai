"""Public web-chat exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class WebChatNotFoundError(BaseError):
    """Raised for invalid tokens or executions outside the exposed workflow."""

    def __init__(
        self,
        message: str = "Web chat not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
