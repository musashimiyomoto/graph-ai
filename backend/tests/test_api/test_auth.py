"""Auth API tests."""

import secrets
import uuid

import pytest

from settings import auth_settings
from tests.factories import UserFactory
from tests.test_api.base import BaseTestCase
from utils.crypto import hash_password


class TestAuthRegister(BaseTestCase):
    """Tests for POST /auth/register."""

    url = "/auth/register"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful registration returns user data."""
        payload = {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": secrets.token_urlsafe(16),
        }

        response = await self.client.post(url=self.url, json=payload)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"id", "email", "created_at", "updated_at"})
        if data["email"] != payload["email"]:
            pytest.fail("Response email did not match request")
        if "hashed_password" in data:
            pytest.fail("Response must not include 'hashed_password'")
        if "password" in data:
            pytest.fail("Response must not include 'password'")


class TestAuthLogin(BaseTestCase):
    """Tests for POST /auth/login."""

    url = "/auth/login"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful login returns access token."""
        user_data = {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": secrets.token_urlsafe(16),
        }
        await UserFactory.create_async(
            session=self.session,
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
        )

        response = await self.client.post(
            url=self.url,
            json={"email": user_data["email"], "password": user_data["password"]},
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"access_token", "token_type"})
        if data["token_type"] != auth_settings.token_type:
            pytest.fail("Token type did not match expected value")
