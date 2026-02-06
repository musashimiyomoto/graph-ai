"""Auth API tests."""

import uuid

import pytest

from settings import auth_settings
from tests.factories import UserFactory
from tests.test_api.base import BaseTestCase
from utils.crypto import hash_password


class TestAuthRegister(BaseTestCase):
    """Tests for POST /auth/register."""

    url = "/auth/register"

    def _user_data(self) -> dict:
        return {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": "secure_password123",
        }

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful registration returns user data."""
        user_data = self._user_data()

        response = await self.client.post(url=self.url, json=user_data)

        data = await self.assert_response_ok(response=response)
        assert "id" in data
        assert data["email"] == user_data["email"]
        assert "created_at" in data
        assert "hashed_password" not in data
        assert "password" not in data


class TestAuthLogin(BaseTestCase):
    """Tests for POST /auth/login."""

    url = "/auth/login"

    def _user_data(self) -> dict:
        return {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": "secure_password123",
        }

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful login returns access token."""
        user_data = self._user_data()
        await UserFactory.create_async(
            session=self.session,
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
        )

        response = await self.client.post(
            url=self.url,
            json={"email": user_data["email"], "password": user_data["password"]},
        )

        data = await self.assert_response_ok(response=response)
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == auth_settings.token_type
