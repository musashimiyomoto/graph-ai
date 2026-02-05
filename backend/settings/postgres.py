"""Postgres settings."""

from backend.settings.base import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class PostgresSettings(BaseSettings):
    """Configuration for Postgres connections."""

    model_config = SettingsConfigDict(env_prefix="postgres_")

    image: str = Field(default="postgres:14", title="Postgres image")
    host: str = Field(default="postgres", title="Postgres host")
    port: int = Field(default=5432, title="Postgres port")
    user: str = Field(default="postgres", title="Postgres user")
    password: str = Field(default="postgres", title="Postgres password")
    db: str = Field(default="postgres", title="Postgres db")

    @property
    def url(self) -> str:
        """Build the async SQLAlchemy connection URL."""
        return (
            f"postgresql+asyncpg://"
            f"{self.user}:"
            f"{self.password}@"
            f"{self.host}:"
            f"{self.port}/"
            f"{self.db}"
        )


postgres_settings = PostgresSettings()
