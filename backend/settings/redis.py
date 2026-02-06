"""Settings for the Redis service."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class RedisSettings(BaseSettings):
    """Configuration for Redis service connectivity."""

    model_config = SettingsConfigDict(env_prefix="redis_")

    image: str = Field(default="redis:7.2.4", title="Redis image")
    host: str = Field(default="redis", title="Redis host")
    port: int = Field(default=6379, title="Redis port")
    db: int = Field(default=0, title="Redis db")


redis_settings = RedisSettings()
