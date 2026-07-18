"""PostgreSQL connection exceptions."""

from http import HTTPStatus

from exceptions.base import BaseError


class PostgresConnectionNotFoundError(BaseError):
    """Raised when a saved PostgreSQL connection cannot be found."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="PostgreSQL connection not found", status_code=HTTPStatus.NOT_FOUND
        )


class PostgresConnectionAlreadyExistsError(BaseError):
    """Raised when a connection name is already used by the account."""

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            message="A PostgreSQL connection with this name already exists",
            status_code=HTTPStatus.CONFLICT,
        )
