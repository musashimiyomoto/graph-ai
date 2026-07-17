"""Webhook channel exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class WebhookNotFoundError(BaseError):
    """Raised for an invalid token or a workflow without webhook input enabled."""

    def __init__(
        self,
        message: str = "Webhook not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class WebhookConnectionError(BaseError):
    """Raised when delivering a workflow result to an outbound webhook fails."""

    def __init__(
        self,
        message: str = "Webhook delivery failed",
        status_code: HTTPStatus = HTTPStatus.BAD_GATEWAY,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
