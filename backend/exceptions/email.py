"""Email channel errors."""

from http import HTTPStatus

from exceptions.base import BaseError


class EmailAccountNotFoundError(BaseError):
    """Raised when an email account cannot be found."""

    def __init__(
        self,
        message: str = "Email account not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class EmailAccountConfigError(BaseError):
    """Raised when email transport settings conflict."""

    def __init__(
        self,
        message: str = "Invalid email account configuration",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class EmailConnectionError(BaseError):
    """Raised when IMAP or SMTP communication fails."""

    retryable = True

    def __init__(
        self,
        message: str = "Email server request failed",
        status_code: HTTPStatus = HTTPStatus.BAD_GATEWAY,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
