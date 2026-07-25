"""Telegram bot API tests."""

import uuid

import pytest

from credentials import connection_secret
from db.repositories import ConnectionRepository, TelegramBotRepository
from tests.factories import TelegramBotFactory, UserFactory
from tests.test_api.base import BaseTestCase


class TestTelegramBotCreate(BaseTestCase):
    """Tests for POST /telegram-bots."""

    url = "/telegram-bots"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns bot data."""
        user, headers = await self.create_user_and_get_token()
        payload = {
            "name": f"bot-{uuid.uuid4().hex[:8]}",
            "bot_token": "123456:ABC-DEF",
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"id", "user_id", "name", "enabled"})
        if data["name"] != payload["name"]:
            pytest.fail("Bot name did not match request")
        if data["user_id"] != user["id"]:
            pytest.fail("Bot user_id did not match current user")
        if not data["enabled"]:
            pytest.fail("Bot should default to enabled")

    @pytest.mark.asyncio
    async def test_bot_token_stored_encrypted_and_not_returned(self) -> None:
        """A provided bot token is encrypted at rest and never returned."""
        _, headers = await self.create_user_and_get_token()
        plaintext = "123456:ABC-DEF"
        payload = {
            "name": f"bot-{uuid.uuid4().hex[:8]}",
            "bot_token": plaintext,
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        if "bot_token" in data:
            pytest.fail("Bot token must never appear in the response")

        stored = await TelegramBotRepository().get_by(
            session=self.session, id=data["id"]
        )
        if stored is None:
            pytest.fail("Expected the bot to persist")
            return
        connection = await ConnectionRepository().get_by(
            session=self.session, id=stored.connection_id
        )
        if connection is None:
            pytest.fail("Expected the bot credential connection to persist")
        elif plaintext in connection.credentials:
            pytest.fail("Bot token must be stored encrypted, not as plaintext")
        elif connection_secret(connection) != plaintext:
            pytest.fail("Stored bot token must decrypt back to the original value")


class TestTelegramBotList(BaseTestCase):
    """Tests for GET /telegram-bots."""

    url = "/telegram-bots"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns bots for the current user only."""
        user, headers = await self.create_user_and_get_token()
        other = await UserFactory.create_async(session=self.session)

        mine = await TelegramBotFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        others_bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=other.id
        )

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if mine.id not in ids:
            pytest.fail("Expected bot to appear in list")
        if others_bot.id in ids:
            pytest.fail("Unexpected bot from another user in list")


class TestTelegramBotUpdate(BaseTestCase):
    """Tests for PATCH /telegram-bots/{bot_id}."""

    url = "/telegram-bots"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated bot data."""
        user, headers = await self.create_user_and_get_token()
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        new_name = f"bot-{uuid.uuid4().hex[:8]}"

        response = await self.client.patch(
            url=f"{self.url}/{bot.id}",
            json={"name": new_name, "enabled": False},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != new_name:
            pytest.fail("Bot name was not updated")
        if data["enabled"]:
            pytest.fail("Bot enabled flag was not updated")


class TestTelegramBotDelete(BaseTestCase):
    """Tests for DELETE /telegram-bots/{bot_id}."""

    url = "/telegram-bots"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the bot."""
        user, headers = await self.create_user_and_get_token()
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user["id"]
        )

        response = await self.client.delete(
            url=f"{self.url}/{bot.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(url=self.url, headers=headers)
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if bot.id in ids:
            pytest.fail("Expected deleted bot to not appear in list")
