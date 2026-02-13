"""Settings exports."""

from settings.auth import auth_settings
from settings.ollama import ollama_settings
from settings.postgres import postgres_settings

__all__ = ["auth_settings", "ollama_settings", "postgres_settings"]
