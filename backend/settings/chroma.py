"""Settings for the Chroma service."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class ChromaSettings(BaseSettings):
    """Configuration for Chroma service connectivity."""

    model_config = SettingsConfigDict(env_prefix="chroma_")

    image: str = Field(default="chromadb/chroma:1.0.20", title="Chroma image")
    host: str = Field(default="chroma", title="Chroma host")
    port: int = Field(default=8000, title="Chroma port")

    @property
    def url(self) -> str:
        """Return the base URL for the Chroma service."""
        return f"http://{self.host}:{self.port}"


chroma_settings = ChromaSettings()
