"""PostgreSQL connection dependency providers."""

from usecases import PostgresConnectionUsecase


def get_postgres_connection_usecase() -> PostgresConnectionUsecase:
    """Build a PostgreSQL connection usecase."""
    return PostgresConnectionUsecase()
