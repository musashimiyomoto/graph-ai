"""LLM provider model factory."""

from factory.declarations import LazyAttribute

from db.models import LLMProvider
from enums import LLMProviderType
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class LLMProviderFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating LLMProvider instances."""

    class Meta:
        """Factory meta configuration."""

        model = LLMProvider

    user_id = None
    name = LazyAttribute(lambda _obj: f"provider-{fake.word()}")
    type = LLMProviderType.OLLAMA
    config = LazyAttribute(lambda _obj: {})
    base_url = LazyAttribute(lambda _obj: fake.url())
