"""Auth API tests."""

import secrets
import uuid
from http import HTTPStatus

import pytest
from jose import jwt

from api.dependencies import auth as auth_dependency
from db.repositories import (
    AuthActionTokenRepository,
    AuthSessionRepository,
    LLMProviderRepository,
)
from enums import LLMProviderType
from main import app
from settings import auth_settings
from tests.factories import UserFactory
from tests.test_api.base import BaseTestCase
from usecases import AuthUsecase
from utils.crypto import hash_password


class _CapturingAuthEmailSender:
    """Capture opaque account links instead of sending SMTP messages."""

    def __init__(self) -> None:
        """Initialize empty delivery lists."""
        self.verifications: list[tuple[str, str]] = []
        self.password_resets: list[tuple[str, str]] = []

    async def send_verification(self, recipient: str, token: str) -> None:
        """Capture a verification delivery."""
        self.verifications.append((recipient, token))

    async def send_password_reset(self, recipient: str, token: str) -> None:
        """Capture a password reset delivery."""
        self.password_resets.append((recipient, token))


def _capture_account_emails() -> _CapturingAuthEmailSender:
    """Override the auth usecase with one deterministic email sender."""
    sender = _CapturingAuthEmailSender()
    app.dependency_overrides[auth_dependency.get_auth_usecase] = lambda: AuthUsecase(
        email_sender=sender
    )
    return sender


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


class TestAccountSecurity(BaseTestCase):
    """Email verification and password recovery API tests."""

    @pytest.mark.asyncio
    async def test_registration_requires_one_time_email_verification(self) -> None:
        """A new account cannot sign in until its hashed link is consumed once."""
        sender = _capture_account_emails()
        email = f"verify-{uuid.uuid4().hex[:8]}@example.com"
        password = secrets.token_urlsafe(16)

        register_response = await self.client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        registered = await self.assert_response_dict(response=register_response)
        if registered["email_verified_at"] is not None:
            pytest.fail("New registrations must start unverified")
        if len(sender.verifications) != 1:
            pytest.fail("Registration should send exactly one verification email")
        raw_token = sender.verifications[0][1]
        action_tokens = await AuthActionTokenRepository().get_all(
            session=self.session,
            user_id=registered["id"],
        )
        if len(action_tokens) != 1 or raw_token in action_tokens[0].token_hash:
            pytest.fail("Only a one-way token hash should be stored")

        blocked = await self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        if blocked.status_code != HTTPStatus.FORBIDDEN:
            pytest.fail("Unverified accounts must not be allowed to sign in")

        verified = await self.client.post(
            "/auth/verify-email",
            json={"token": raw_token},
        )
        await self.assert_response_ok(response=verified)
        reused = await self.client.post(
            "/auth/verify-email",
            json={"token": raw_token},
        )
        if reused.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("A verification token must only work once")
        login_response = await self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        await self.assert_response_dict(response=login_response)

    @pytest.mark.asyncio
    async def test_resend_replaces_the_previous_verification_link(self) -> None:
        """Requesting a new verification email invalidates an older link."""
        sender = _capture_account_emails()
        email = f"resend-{uuid.uuid4().hex[:8]}@example.com"
        await self.client.post(
            "/auth/register",
            json={"email": email, "password": secrets.token_urlsafe(16)},
        )
        first_token = sender.verifications[-1][1]

        response = await self.client.post(
            "/auth/resend-verification",
            json={"email": email},
        )
        await self.assert_response_ok(response=response)
        second_token = sender.verifications[-1][1]
        if second_token == first_token:
            pytest.fail("A resend should rotate the verification token")
        stale = await self.client.post(
            "/auth/verify-email",
            json={"token": first_token},
        )
        if stale.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("The prior verification token should be invalidated")

    @pytest.mark.asyncio
    async def test_password_reset_is_generic_and_revokes_sessions(self) -> None:
        """Recovery hides account existence, rotates credentials, and signs out."""
        sender = _capture_account_emails()
        old_password = secrets.token_urlsafe(16)
        new_password = secrets.token_urlsafe(16)
        user = await UserFactory.create_async(
            session=self.session,
            email=f"recovery-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password(old_password),
        )
        await self.client.post(
            "/auth/login",
            json={"email": user.email, "password": old_password},
        )

        known = await self.client.post(
            "/auth/forgot-password",
            json={"email": user.email},
        )
        unknown = await self.client.post(
            "/auth/forgot-password",
            json={"email": f"missing-{uuid.uuid4().hex}@example.com"},
        )
        known_data = await self.assert_response_dict(response=known)
        unknown_data = await self.assert_response_dict(response=unknown)
        if known_data != unknown_data:
            pytest.fail("Recovery responses must not reveal account existence")
        reset_token = sender.password_resets[-1][1]

        reset_response = await self.client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": new_password},
        )
        await self.assert_response_ok(response=reset_response)
        sessions = await AuthSessionRepository().get_all(
            session=self.session,
            user_id=user.id,
        )
        if not sessions or any(item.revoked_at is None for item in sessions):
            pytest.fail("Password reset must revoke every existing session")
        reused = await self.client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": old_password},
        )
        if reused.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("A password reset token must only work once")
        old_login = await self.client.post(
            "/auth/login",
            json={"email": user.email, "password": old_password},
        )
        if old_login.status_code != HTTPStatus.UNAUTHORIZED:
            pytest.fail("The old password must stop working after recovery")
        new_login = await self.client.post(
            "/auth/login",
            json={"email": user.email, "password": new_password},
        )
        await self.assert_response_dict(response=new_login)

    @pytest.mark.asyncio
    async def test_authenticated_password_change_revokes_access(self) -> None:
        """Changing the current password invalidates the current access session."""
        old_password = secrets.token_urlsafe(16)
        new_password = secrets.token_urlsafe(16)
        user, headers = await self.create_user_and_get_token(password=old_password)

        changed = await self.client.post(
            "/auth/change-password",
            headers=headers,
            json={
                "current_password": old_password,
                "new_password": new_password,
            },
        )
        await self.assert_response_ok(response=changed)
        invalidated = await self.client.get("/users/me", headers=headers)
        if invalidated.status_code != HTTPStatus.UNAUTHORIZED:
            pytest.fail("Password change must invalidate existing access tokens")
        new_login = await self.client.post(
            "/auth/login",
            json={"email": user["email"], "password": new_password},
        )
        await self.assert_response_dict(response=new_login)
