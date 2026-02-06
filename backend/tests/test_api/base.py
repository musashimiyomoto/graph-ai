"""Shared test helpers and base classes."""

import uuid
from http import HTTPStatus

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
            raise AssertionError(message)
        return response.json()

    async def create_user_and_get_token(
        self,
        email: str | None = None,
        password: str = "secure_password123",
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
