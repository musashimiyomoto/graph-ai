"""Telegram bot model factory."""

from factory.declarations import LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TelegramBot
from tests.factories.base import AsyncSQLAlchemyModelFactory, ModelT, fake
from tests.factories.connection import ConnectionFactory


class TelegramBotFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating TelegramBot instances."""

    class Meta:
        """Factory meta configuration."""

        model = TelegramBot

    user_id = None
    name = LazyAttribute(lambda _obj: f"bot-{fake.word()}")
    last_update_id = 0
    enabled = True

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: object) -> ModelT:
        """Create the unified credential row before the bot profile."""
        connection = await ConnectionFactory.create_async(
            session=session,
            user_id=kwargs.get("user_id"),
            provider="telegram",
        )
        kwargs["connection_id"] = connection.id
        return await super().create_async(session=session, **kwargs)
