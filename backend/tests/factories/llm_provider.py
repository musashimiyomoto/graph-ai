"""LLM provider model factory."""

import secrets

from factory.declarations import LazyAttribute

from enums import LLMProviderType
from models.llm_provider import LLMProvider
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class LLMProviderFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating LLMProvider instances."""

    class Meta:
        """Factory meta configuration."""

        model = LLMProvider

    user_id = None
    name = LazyAttribute(lambda _obj: f"provider-{fake.word()}")
    type = LLMProviderType.OLLAMA
    api_key = LazyAttribute(lambda _obj: secrets.token_urlsafe(18))
    base_url = None
    is_default = False
