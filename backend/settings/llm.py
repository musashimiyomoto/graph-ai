"""Settings for generic LLM client configuration."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class LLMSettings(BaseSettings):
    """Configuration for LLM client defaults."""

    model_config = SettingsConfigDict(env_prefix="llm_")

    default_base_url: str = Field(
        default="http://ollama:11434", title="Default LLM base URL"
    )
    request_timeout: float = Field(default=10.0, title="LLM request timeout (seconds)")


llm_settings = LLMSettings()
