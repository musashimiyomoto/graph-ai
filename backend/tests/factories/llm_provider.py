"""LLM provider model factory."""

from factory.declarations import LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession

from credentials import seal_credentials
from db.models import LLMProvider
from enums import LLMProviderType
from tests.factories.base import AsyncSQLAlchemyModelFactory, ModelT, fake
from tests.factories.connection import ConnectionFactory


class LLMProviderFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating LLMProvider instances."""

    class Meta:
        """Factory meta configuration."""

        model = LLMProvider

    user_id = None
    name = LazyAttribute(lambda _obj: f"provider-{fake.word()}")
    type = LLMProviderType.OLLAMA
    config = LazyAttribute(lambda _obj: {})
    # Provider URLs allow private/loopback hosts; keeping this deterministic
    # avoids test behavior depending on how a generated public domain resolves.
    base_url = "http://localhost:11434"

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: object) -> ModelT:
        """Create the unified credential row before the provider profile."""
        api_key = kwargs.pop("api_key", None)
        if api_key is not None and not isinstance(api_key, str):
            message = "LLMProviderFactory api_key must be a string"
            raise TypeError(message)
        provider_type = kwargs.get("type", LLMProviderType.OLLAMA)
        if not isinstance(provider_type, LLMProviderType):
            message = "LLMProviderFactory type must be an LLMProviderType"
            raise TypeError(message)
        user_id = kwargs.get("user_id")
        connection = await ConnectionFactory.create_async(
            session=session,
            user_id=user_id,
            provider=f"llm_{provider_type.value}",
            credentials=seal_credentials({"secret": api_key or "factory-secret"}),
        )
        kwargs["connection_id"] = connection.id
        return await super().create_async(session=session, **kwargs)
