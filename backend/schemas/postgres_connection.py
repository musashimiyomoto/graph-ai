"""Schemas for saved PostgreSQL connections."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_dsn(value: str) -> str:
    """Require a PostgreSQL DSN without exposing it in responses."""
    if not value.startswith(("postgresql://", "postgres://")):
        message = "DSN must start with postgresql:// or postgres://"
        raise ValueError(message)
    return value


class PostgresConnectionCreate(BaseModel):
    """Payload for creating a PostgreSQL connection."""

    name: str = Field(default=..., min_length=1, max_length=128)
    dsn: str = Field(default=..., min_length=1, max_length=2048)

    @field_validator("dsn")
    @classmethod
    def validate_dsn(cls, value: str) -> str:
        """Validate the connection string scheme."""
        return _validate_dsn(value)


class PostgresConnectionResponse(BaseModel):
    """Public connection metadata; the DSN is intentionally write-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., gt=0)
    user_id: int = Field(default=..., gt=0)
    connection_id: int = Field(default=..., gt=0)
    name: str
