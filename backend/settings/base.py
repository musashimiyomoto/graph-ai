"""Base settings configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict

BASE_PATH = Path(__file__).parent.parent.parent


class BaseSettings(PydanticBaseSettings):
    """Base settings shared across environments."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=f"{BASE_PATH}/.env",
        extra="ignore",
    )
