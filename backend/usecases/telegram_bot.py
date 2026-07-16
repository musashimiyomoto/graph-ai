"""Telegram bot use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import TelegramBotRepository
from exceptions import TelegramBotNotFoundError
from schemas import TelegramBotCreate, TelegramBotResponse, TelegramBotUpdate
from usecases.audit import AuditEvent, AuditUsecase
from utils.encryption import encrypt


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
        bot = await self._telegram_bot_repository.create(
            session=session,
            data={
                "user_id": user_id,
                "name": data.name,
                "bot_token": encrypt(data.bot_token),
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
        bot = await self.get_telegram_bot(
            session=session, bot_id=bot_id, user_id=user_id
        )

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return bot

        if "bot_token" in update_data:
            update_data["bot_token"] = encrypt(update_data["bot_token"])

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
        deleted = await self._telegram_bot_repository.delete_by(
            session=session, id=bot_id, user_id=user_id
        )
        if not deleted:
            raise TelegramBotNotFoundError
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
