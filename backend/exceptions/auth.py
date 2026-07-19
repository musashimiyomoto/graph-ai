"""Auth-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class AuthCredentialsError(BaseError):
    """Raised when auth credentials are invalid."""

    def __init__(
        self,
        message: str = "Could not validate credentials",
        status_code: HTTPStatus = HTTPStatus.UNAUTHORIZED,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class AuthSessionNotFoundError(BaseError):
    """Raised when an owned login session is not found."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="Authentication session not found",
            status_code=HTTPStatus.NOT_FOUND,
        )


class EmailNotVerifiedError(BaseError):
    """Raised when valid credentials belong to an unverified account."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="Verify your email before signing in",
            status_code=HTTPStatus.FORBIDDEN,
        )


class AuthActionTokenError(BaseError):
    """Raised when an account action token is invalid or expired."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="This link is invalid or has expired",
            status_code=HTTPStatus.BAD_REQUEST,
        )


class CurrentPasswordError(BaseError):
    """Raised when the supplied current password is incorrect."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="Current password is incorrect",
            status_code=HTTPStatus.BAD_REQUEST,
        )


class PasswordUnchangedError(BaseError):
    """Raised when a new password matches the current password."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="New password must differ from the current password",
            status_code=HTTPStatus.BAD_REQUEST,
        )
