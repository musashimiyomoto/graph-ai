"""Settings for the Ollama service."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class OllamaSettings(BaseSettings):
    """Configuration for Ollama service connectivity."""

    model_config = SettingsConfigDict(env_prefix="ollama_")

    image: str = Field(default="ollama/ollama:latest", title="Ollama image")
    host: str = Field(default="ollama", title="Ollama host")
    port: int = Field(default=11434, title="Ollama port")

    @property
    def url(self) -> str:
        """Return the base URL for the Ollama service."""
        return f"http://{self.host}:{self.port}"


ollama_settings = OllamaSettings()
