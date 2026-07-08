"""RAG (vector store) related exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class VectorCollectionNotFoundError(BaseError):
    """Raised when a Qdrant collection doesn't exist."""

    def __init__(
        self,
        message: str = "Vector collection not found",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class VectorDocumentNotFoundError(BaseError):
    """Raised when a document (source) has no points in a collection."""

    def __init__(
        self,
        message: str = "Document not found in collection",
        status_code: HTTPStatus = HTTPStatus.NOT_FOUND,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class UnsupportedDocumentTypeError(BaseError):
    """Raised when an uploaded document can't be parsed into text."""

    def __init__(
        self,
        message: str = "Unsupported document type",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class DocumentTooLargeError(BaseError):
    """Raised when an uploaded document exceeds the size cap."""

    def __init__(
        self,
        message: str = "Document is too large",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)


class EmptyDocumentError(BaseError):
    """Raised when a document contains no extractable text to ingest."""

    def __init__(
        self,
        message: str = "Document contains no extractable text",
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        """Initialize the error."""
        super().__init__(message=message, status_code=status_code)
