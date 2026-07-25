"""Telegram bot use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from credentials import create_profile_connection, update_profile_connection
from db.repositories import ConnectionRepository, TelegramBotRepository
from exceptions import TelegramBotNotFoundError
from schemas import TelegramBotCreate, TelegramBotResponse, TelegramBotUpdate
from usecases.audit import AuditEvent, AuditUsecase


class TelegramBotUsecase:
    """Telegram bot business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._telegram_bot_repository = TelegramBotRepository()
        self._audit_usecase = AuditUsecase()

    async def create_telegram_bot(
        self,
        session: AsyncSession,
        user_id: int,
        data: TelegramBotCreate,
    ) -> TelegramBotResponse:
        """Create a new Telegram bot.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The bot creation fields.

        Returns:
            The created Telegram bot.

        """
        connection = await create_profile_connection(
            session=session,
            user_id=user_id,
            name=data.name,
            provider="telegram",
            secret=data.bot_token,
        )
        bot = await self._telegram_bot_repository.create(
            session=session,
            data={
                "user_id": user_id,
                "name": data.name,
                "connection_id": connection.id,
            },
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="telegram_bot.create",
                entity_type="telegram_bot",
                entity_id=bot.id,
                metadata={"name": bot.name},
            ),
        )
        await session.commit()
        return TelegramBotResponse.model_validate(bot)

    async def get_telegram_bots(
        self, session: AsyncSession, user_id: int
    ) -> list[TelegramBotResponse]:
        """List Telegram bots for a user.

        Args:
            session: The session.
            user_id: The owner user ID.

        Returns:
            The list of Telegram bots.

        """
        return [
            TelegramBotResponse.model_validate(bot)
            for bot in await self._telegram_bot_repository.get_all(
                session=session, user_id=user_id
            )
        ]

    async def get_telegram_bot(
        self, session: AsyncSession, bot_id: int, user_id: int
    ) -> TelegramBotResponse:
        """Fetch a Telegram bot by ID.

        Args:
            session: The session.
            bot_id: The bot ID.
            user_id: The owner user ID.

        Returns:
            The Telegram bot.

        Raises:
            TelegramBotNotFoundError: If the bot is not found.

        """
        bot = await self._telegram_bot_repository.get_by(
            session=session, id=bot_id, user_id=user_id
        )
        if not bot:
            raise TelegramBotNotFoundError

        return TelegramBotResponse.model_validate(bot)

    async def update_telegram_bot(
        self,
        session: AsyncSession,
        bot_id: int,
        user_id: int,
        data: TelegramBotUpdate,
    ) -> TelegramBotResponse:
        """Update a Telegram bot by ID.

        Args:
            session: The session.
            bot_id: The bot ID.
            user_id: The owner user ID.
            data: The fields to update.

        Returns:
            The updated Telegram bot.

        Raises:
            TelegramBotNotFoundError: If the bot is not found.

        """
        stored = await self._telegram_bot_repository.get_by(
            session=session, id=bot_id, user_id=user_id
        )
        if stored is None:
            raise TelegramBotNotFoundError
        bot = TelegramBotResponse.model_validate(stored)

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return bot

        replace_secret = "bot_token" in update_data
        bot_token = update_data.pop("bot_token", None)
        await update_profile_connection(
            session=session,
            connection_id=stored.connection_id,
            name=update_data.get("name"),
            secret=bot_token,
            replace_secret=replace_secret,
        )

        updated = await self._telegram_bot_repository.update_by(
            session=session, data=update_data, id=bot_id
        )
        if not updated:
            raise TelegramBotNotFoundError

        await session.commit()
        return TelegramBotResponse.model_validate(updated)

    async def delete_telegram_bot(
        self, session: AsyncSession, bot_id: int, user_id: int
    ) -> None:
        """Delete a Telegram bot by ID.

        Args:
            session: The session.
            bot_id: The bot ID.
            user_id: The owner user ID.

        Raises:
            TelegramBotNotFoundError: If the bot is not found.

        """
        bot = await self._telegram_bot_repository.get_by(
            session=session, id=bot_id, user_id=user_id
        )
        if bot is None:
            raise TelegramBotNotFoundError
        await ConnectionRepository().delete_by(
            session=session, id=bot.connection_id, user_id=user_id
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="telegram_bot.delete",
                entity_type="telegram_bot",
                entity_id=bot_id,
            ),
        )
        await session.commit()
