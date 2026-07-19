"""Auth API tests."""

import secrets
import uuid
from http import HTTPStatus

import pytest
from jose import jwt

from db.repositories import AuthSessionRepository, LLMProviderRepository
from enums import LLMProviderType
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

    @pytest.mark.asyncio
    async def test_creates_default_ollama_provider(self) -> None:
        """Registration creates a default local Ollama provider."""
        payload = {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": secrets.token_urlsafe(16),
        }

        response = await self.client.post(url=self.url, json=payload)
        data = await self.assert_response_dict(response=response)

        providers = await LLMProviderRepository().get_all(
            session=self.session, user_id=data["id"]
        )

        if len(providers) != 1:
            pytest.fail("Expected exactly one default LLM provider for new user")

        provider = providers[0]
        if provider.type != LLMProviderType.OLLAMA:
            pytest.fail("Expected default provider type to be OLLAMA")
        if provider.name != "ollama":
            pytest.fail("Expected default provider name to be 'ollama'")

    @pytest.mark.asyncio
    async def test_short_password_rejected(self) -> None:
        """A password under 8 characters is rejected."""
        payload = {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": "short1",
        }

        response = await self.client.post(url=self.url, json=payload)

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail(f"Expected a validation error, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_long_password_rejected(self) -> None:
        """A password over 72 characters is rejected."""
        payload = {
            "email": f"john.doe-{uuid.uuid4().hex[:8]}@example.com",
            "password": "x" * 73,
        }

        response = await self.client.post(url=self.url, json=payload)

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail(f"Expected a validation error, got {response.status_code}")


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

    @pytest.mark.asyncio
    async def test_token_includes_iat_and_jti(self) -> None:
        """The issued access token carries iat/jti claims."""
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

        payload = jwt.decode(
            token=data["access_token"],
            key=auth_settings.secret_key,
            algorithms=[auth_settings.algorithm],
        )
        self.assert_has_keys(payload, {"exp", "iat", "jti", "sub"})

    @pytest.mark.asyncio
    async def test_refresh_rotates_cookie_and_database_hash(self) -> None:
        """Refresh tokens are opaque, rotated, and stored only as hashes."""
        password = secrets.token_urlsafe(16)
        user = await UserFactory.create_async(
            session=self.session,
            email=f"refresh-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password(password),
        )
        login_response = await self.client.post(
            url=self.url,
            json={"email": user.email, "password": password},
        )
        await self.assert_response_dict(response=login_response)
        first_cookie = login_response.cookies.get("graph_ai_refresh")
        if not first_cookie:
            pytest.fail("Login should set an HttpOnly refresh cookie")
        first_cookie_value = str(first_cookie)

        refresh_response = await self.client.post("/auth/refresh")
        await self.assert_response_dict(response=refresh_response)
        second_cookie = refresh_response.cookies.get("graph_ai_refresh")
        if not second_cookie or second_cookie == first_cookie:
            pytest.fail("Refresh should rotate the cookie value")

        sessions = await AuthSessionRepository().get_all(
            session=self.session,
            user_id=user.id,
        )
        if len(sessions) != 1 or first_cookie_value in sessions[0].token_hash:
            pytest.fail("Database should contain one hashed rotated token")

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_session(self) -> None:
        """Logout invalidates the current refresh token."""
        password = secrets.token_urlsafe(16)
        user = await UserFactory.create_async(
            session=self.session,
            email=f"logout-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password(password),
        )
        await self.client.post(
            url=self.url,
            json={"email": user.email, "password": password},
        )

        logout_response = await self.client.post("/auth/logout")
        await self.assert_response_ok(response=logout_response)
        refresh_response = await self.client.post("/auth/refresh")
        if refresh_response.status_code != HTTPStatus.UNAUTHORIZED:
            pytest.fail("Logged-out refresh token should be rejected")

    @pytest.mark.asyncio
    async def test_sessions_can_be_listed_and_revoked(self) -> None:
        """Users can inspect and revoke their active browser sessions."""
        password = secrets.token_urlsafe(16)
        user = await UserFactory.create_async(
            session=self.session,
            email=f"sessions-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password(password),
        )
        first = await self.client.post(
            url=self.url,
            json={"email": user.email, "password": password},
        )
        first_data = await self.assert_response_dict(response=first)
        second = await self.client.post(
            url=self.url,
            json={"email": user.email, "password": password},
        )
        second_data = await self.assert_response_dict(response=second)
        response = await self.client.get(
            "/auth/sessions",
            headers={"Authorization": f"Bearer {second_data['access_token']}"},
        )
        sessions = await self.assert_response_list(response=response)
        expected_session_count = 2
        if (
            len(sessions) != expected_session_count
            or sum(item["current"] for item in sessions) != 1
        ):
            pytest.fail(
                "Session list should identify both sessions and the current one"
            )
        old_session = next(item for item in sessions if not item["current"])
        revoke_response = await self.client.delete(
            f"/auth/sessions/{old_session['id']}",
            headers={"Authorization": f"Bearer {first_data['access_token']}"},
        )
        await self.assert_response_ok(response=revoke_response)
        rejected = await self.client.get(
            "/auth/sessions",
            headers={"Authorization": f"Bearer {first_data['access_token']}"},
        )
        if rejected.status_code != HTTPStatus.UNAUTHORIZED:
            pytest.fail(
                "Revoking a session should immediately invalidate its access token"
            )
