"""Artifact-domain exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class ArtifactNotFoundError(BaseError):
    """Raised when an owned artifact does not exist."""

    def __init__(self, message: str = "Artifact not found") -> None:
        """Initialize a not-found error."""
        super().__init__(message=message, status_code=HTTPStatus.NOT_FOUND)


class ArtifactExpiredError(BaseError):
    """Raised when an artifact passed its retention deadline."""

    def __init__(self, message: str = "Artifact has expired") -> None:
        """Initialize an expired-resource error."""
        super().__init__(message=message, status_code=HTTPStatus.GONE)


class ArtifactTooLargeError(BaseError):
    """Raised when one upload exceeds the configured size cap."""

    def __init__(self, message: str = "Artifact exceeds the upload size limit") -> None:
        """Initialize a payload-too-large error."""
        super().__init__(
            message=message,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )


class ArtifactQuotaExceededError(BaseError):
    """Raised when retaining an upload would exceed the user's byte quota."""

    def __init__(self, message: str = "Artifact storage quota exceeded") -> None:
        """Initialize a quota error."""
        super().__init__(message=message, status_code=HTTPStatus.TOO_MANY_REQUESTS)


class EmptyArtifactError(BaseError):
    """Raised when an upload has no bytes."""

    def __init__(self, message: str = "Artifact upload is empty") -> None:
        """Initialize an empty-upload error."""
        super().__init__(message=message, status_code=HTTPStatus.UNPROCESSABLE_ENTITY)


class ArtifactStorageError(BaseError):
    """Raised when S3-compatible storage is unavailable."""

    retryable = True

    def __init__(self, message: str = "Artifact storage is unavailable") -> None:
        """Initialize an upstream-storage error."""
        super().__init__(message=message, status_code=HTTPStatus.BAD_GATEWAY)
