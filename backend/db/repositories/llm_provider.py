"""Repository for LLM providers."""

from db.models import LLMProvider
from db.repositories.base import BaseRepository


class LLMProviderRepository(BaseRepository[LLMProvider]):
    """Repository for LLMProvider model operations."""

    def __init__(self) -> None:
        """Initialize the repository with the LLMProvider model."""
        super().__init__(model=LLMProvider)
