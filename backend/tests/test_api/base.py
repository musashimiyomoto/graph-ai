"""Shared test helpers and base classes."""

import secrets
import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from settings import auth_settings
from tests.factories.user import UserFactory
from utils.crypto import hash_password


class BaseTestCase:
    """Base test case with shared fixtures and assertions."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, test_session: AsyncSession, test_client: AsyncClient) -> None:
        """Attach the test session and client to the instance."""
        self.session = test_session
        self.client = test_client

    async def assert_response_ok(self, response: Response) -> dict:
        """Assert a response has an OK/ACCEPTED status and return JSON."""
        if response.status_code not in {HTTPStatus.OK, HTTPStatus.ACCEPTED}:
            message = (
                f"Expected response status OK or ACCEPTED, got {response.status_code}"
            )
            pytest.fail(message)
        return response.json()

    async def assert_response_dict(self, response: Response) -> dict[str, Any]:
        """Assert response OK and JSON object."""
        data = await self.assert_response_ok(response=response)
        if not isinstance(data, dict):
            pytest.fail("Expected response to be an object")
        return data

    async def assert_response_list(self, response: Response) -> list[dict[str, Any]]:
        """Assert response OK and JSON array of objects."""
        data = await self.assert_response_ok(response=response)
        if not isinstance(data, list):
            pytest.fail("Expected response to be a list")
        return [item for item in data if isinstance(item, dict)]

    def assert_has_keys(self, payload: Mapping[str, object], keys: set[str]) -> None:
        """Assert a mapping contains the required keys."""
        missing = {key for key in keys if key not in payload}
        if missing:
            pytest.fail(f"Response missing keys: {sorted(missing)}")

    async def create_user_and_get_token(
        self,
        email: str | None = None,
        password: str | None = None,
    ) -> tuple[dict, dict]:
        """Create a user and return their data with auth headers.

        Args:
            email: The user email.
            password: The user password.

        Returns:
            A tuple of user data dict and authorization headers dict.

        """
        if email is None:
            email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        if password is None:
            password = secrets.token_urlsafe(16)

        user = await UserFactory.create_async(
            session=self.session,
            email=email,
            hashed_password=hash_password(password),
        )

        response = await self.client.post(
            url="/auth/login", json={"email": email, "password": password}
        )

        return user.__dict__, {
            "Authorization": (
                f"{auth_settings.token_type} {response.json()['access_token']}"
            )
        }
