"""LLM provider-related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class LLMProviderNotFoundError(BaseError):
    """Raised when an LLM provider cannot be found."""

    def __init__(
        self,
        message: str = "LLM provider not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class LLMProviderConnectionError(BaseError):
    """Raised when the LLM provider is unreachable."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="LLM provider is unreachable",
            status_code=HTTPStatus.BAD_GATEWAY,
        )
