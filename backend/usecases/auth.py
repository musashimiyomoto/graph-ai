"""Auth use case implementation."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuthActionToken
from db.repositories import (
    AuthActionTokenRepository,
    AuthSessionRepository,
    LLMProviderRepository,
    UserRepository,
)
from enums import AuthActionPurpose, LLMProviderType
from exceptions import (
    AuthActionTokenError,
    AuthCredentialsError,
    AuthSessionNotFoundError,
    CurrentPasswordError,
    EmailConnectionError,
    EmailNotVerifiedError,
    PasswordUnchangedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from integrations.auth_email import AuthEmailSender, SMTPAuthEmailSender
from schemas import (
    AuthSessionResponse,
    LoginCreate,
    LoginResponse,
    UserCreate,
    UserResponse,
)
from settings import auth_email_settings, auth_settings, ollama_settings
from usecases.audit import AuditEvent, AuditUsecase
from utils.crypto import hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthUsecase:
    """Auth business logic."""

    def __init__(self, email_sender: AuthEmailSender | None = None) -> None:
        """Initialize the usecase."""
        self._user_repository = UserRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._session_repository = AuthSessionRepository()
        self._action_token_repository = AuthActionTokenRepository()
        self._audit_usecase = AuditUsecase()
        self._email_sender = email_sender or SMTPAuthEmailSender()

    @staticmethod
    def _create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        """Create an access token.

        Args:
            data: The data to encode.
            expires_delta: The expiration time.

        Returns:
            The access token.

        """
        to_encode = data.copy()
        now = datetime.now(tz=UTC)

        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=auth_settings.access_token_expire_minutes)

        # `iat`/`jti` are cheap, forward-compatible groundwork for a future
        # refresh token + revocation list — `jti` gives each token a stable
        # identity a revocation list could key on.
        to_encode.update(
            {
                "exp": expire,
                "iat": now,
                "jti": str(uuid.uuid4()),
                "typ": "access",
            }
        )

        return jwt.encode(
            claims=to_encode,
            key=auth_settings.secret_key,
            algorithm=auth_settings.algorithm,
        )

    def get_payload(self, token: str) -> dict:
        """Get the payload from the token.

        Args:
            token: The token.

        Returns:
            The payload.

        Raises:
            AuthCredentialsError: If the token is invalid.

        """
        try:
            return jwt.decode(
                token=token,
                key=auth_settings.secret_key,
                algorithms=[auth_settings.algorithm],
            )
        except JWTError as e:
            raise AuthCredentialsError from e

    async def _authenticate(
        self, session: AsyncSession, email: str, password: str
    ) -> UserResponse:
        """Authenticate a user.

        Args:
            session: The session.
            email: The email.
            password: The password.

        Returns:
            The user.

        Raises:
            AuthCredentialsError: If the user is not authenticated.

        """
        user = await self._user_repository.get_by(session=session, email=email)

        if (
            not user
            or not user.hashed_password
            or not verify_password(password=password, hashed=user.hashed_password)
        ):
            raise AuthCredentialsError
        if user.email_verified_at is None:
            raise EmailNotVerifiedError

        return UserResponse.model_validate(user)

    async def _get_user_by_email(
        self, session: AsyncSession, email: str
    ) -> UserResponse:
        """Get a user by email.

        Args:
            session: The session.
            email: The email.

        Returns:
            The user.

        Raises:
            UserNotFoundError: If the user is not found.

        """
        user = await self._user_repository.get_by(session=session, email=email)
        if not user:
            raise UserNotFoundError

        return UserResponse.model_validate(user)

    async def get_current_user(
        self,
        session: AsyncSession,
        token: str,
    ) -> UserResponse:
        """Get the current user and check permissions.

        Args:
            session: The session.
            token: The token.

        Returns:
            The user.

        Raises:
            AuthCredentialsError: If the token is invalid.

        """
        payload = self.get_payload(token=token)
        if payload.get("typ") != "access":
            raise AuthCredentialsError
        email = payload.get("sub")
        auth_session_id = payload.get("sid")

        if email is None or not isinstance(auth_session_id, int):
            raise AuthCredentialsError

        auth_session = await self._session_repository.get_by(
            session=session,
            id=auth_session_id,
        )
        now = datetime.now(tz=UTC)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
        ):
            raise AuthCredentialsError
        user = await self._user_repository.get_by(session=session, email=email)

        if not user or user.id != auth_session.user_id:
            raise AuthCredentialsError

        return UserResponse.model_validate(user)

    async def login(
        self,
        session: AsyncSession,
        data: LoginCreate,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[LoginResponse, str]:
        """Login a user.

        Args:
            session: The session.
            data: Login data.
            user_agent: Browser/client user-agent metadata.
            ip_address: Client IP metadata.

        Returns:
            Login response.

        Raises:
            AuthCredentialsError: If the user is not authenticated.

        """
        user = await self._authenticate(
            session=session,
            email=data.email,
            password=data.password,
        )

        if not user:
            raise AuthCredentialsError

        refresh_token = self._new_refresh_token()
        now = datetime.now(tz=UTC)
        auth_session = await self._session_repository.create(
            session=session,
            data={
                "user_id": user.id,
                "token_hash": self._hash_refresh_token(refresh_token),
                "expires_at": now
                + timedelta(days=auth_settings.refresh_token_expire_days),
                "last_used_at": now,
                "user_agent": user_agent,
                "ip_address": ip_address,
            },
        )
        await session.commit()
        return self._login_response(user.email, auth_session.id), refresh_token

    async def refresh(
        self,
        session: AsyncSession,
        refresh_token: str | None,
    ) -> tuple[LoginResponse, str]:
        """Rotate a valid refresh token and issue a new access token."""
        if not refresh_token:
            raise AuthCredentialsError
        auth_session = await self._session_repository.get_by_hash_for_update(
            session=session,
            token_hash=self._hash_refresh_token(refresh_token),
        )
        now = datetime.now(tz=UTC)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
        ):
            raise AuthCredentialsError
        user = await self._user_repository.get_by(
            session=session,
            id=auth_session.user_id,
        )
        if user is None:
            raise AuthCredentialsError
        if user.email_verified_at is None:
            raise AuthCredentialsError
        rotated = self._new_refresh_token()
        auth_session.token_hash = self._hash_refresh_token(rotated)
        auth_session.last_used_at = now
        await session.commit()
        return self._login_response(user.email, auth_session.id), rotated

    async def logout(
        self,
        session: AsyncSession,
        refresh_token: str | None,
    ) -> None:
        """Revoke the current refresh session, if it exists."""
        if refresh_token:
            auth_session = await self._session_repository.get_by(
                session=session,
                token_hash=self._hash_refresh_token(refresh_token),
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = datetime.now(tz=UTC)
                await session.commit()

    async def list_sessions(
        self,
        session: AsyncSession,
        user_id: int,
        refresh_token: str | None,
    ) -> list[AuthSessionResponse]:
        """List active, unexpired sessions for the current account."""
        now = datetime.now(tz=UTC)
        current_hash = (
            self._hash_refresh_token(refresh_token) if refresh_token else None
        )
        sessions = await self._session_repository.get_all(
            session=session,
            user_id=user_id,
            revoked_at=None,
            descending=True,
        )
        return [
            AuthSessionResponse(
                id=item.id,
                created_at=item.created_at,
                last_used_at=item.last_used_at,
                expires_at=item.expires_at,
                user_agent=item.user_agent,
                ip_address=item.ip_address,
                current=item.token_hash == current_hash,
            )
            for item in sessions
            if item.expires_at > now
        ]

    async def revoke_session(
        self,
        session: AsyncSession,
        user_id: int,
        auth_session_id: int,
    ) -> None:
        """Revoke one owned authentication session."""
        auth_session = await self._session_repository.get_by(
            session=session,
            id=auth_session_id,
            user_id=user_id,
        )
        if auth_session is None:
            raise AuthSessionNotFoundError
        if auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(tz=UTC)
            await session.commit()

    async def request_email_verification(
        self,
        session: AsyncSession,
        email: str,
    ) -> None:
        """Issue a fresh verification link when an unverified account exists."""
        user = await self._user_repository.get_by(session=session, email=email)
        if user is None or user.email_verified_at is not None:
            return
        token = await self._issue_action_token(
            session=session,
            user_id=user.id,
            purpose=AuthActionPurpose.VERIFY_EMAIL,
            expires_delta=timedelta(
                hours=auth_email_settings.verification_expire_hours
            ),
        )
        await session.commit()
        await self._send_verification(user.email, token)

    async def verify_email(self, session: AsyncSession, token: str) -> None:
        """Verify email ownership using a one-time token."""
        action_token = await self._get_valid_action_token(
            session=session,
            token=token,
            purpose=AuthActionPurpose.VERIFY_EMAIL,
        )
        user = await self._user_repository.get_by_for_update(
            session=session,
            id=action_token.user_id,
        )
        if user is None:
            raise AuthActionTokenError
        now = datetime.now(tz=UTC)
        user.email_verified_at = user.email_verified_at or now
        action_token.used_at = now
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user.id,
                action="user.email_verify",
                entity_type="user",
                entity_id=user.id,
            ),
        )
        await session.commit()

    async def request_password_reset(
        self,
        session: AsyncSession,
        email: str,
    ) -> None:
        """Issue a password recovery link without exposing account existence."""
        user = await self._user_repository.get_by(session=session, email=email)
        if user is None:
            return
        token = await self._issue_action_token(
            session=session,
            user_id=user.id,
            purpose=AuthActionPurpose.RESET_PASSWORD,
            expires_delta=timedelta(
                minutes=auth_email_settings.password_reset_expire_minutes
            ),
        )
        await session.commit()
        await self._send_password_reset(user.email, token)

    async def reset_password(
        self,
        session: AsyncSession,
        token: str,
        new_password: str,
    ) -> None:
        """Replace a password and revoke all sessions using a recovery token."""
        action_token = await self._get_valid_action_token(
            session=session,
            token=token,
            purpose=AuthActionPurpose.RESET_PASSWORD,
        )
        user = await self._user_repository.get_by_for_update(
            session=session,
            id=action_token.user_id,
        )
        if user is None:
            raise AuthActionTokenError
        if verify_password(password=new_password, hashed=user.hashed_password):
            raise PasswordUnchangedError
        now = datetime.now(tz=UTC)
        user.hashed_password = hash_password(new_password)
        user.email_verified_at = user.email_verified_at or now
        action_token.used_at = now
        await self._session_repository.revoke_all_for_user(
            session=session,
            user_id=user.id,
            revoked_at=now,
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user.id,
                action="user.password_reset",
                entity_type="user",
                entity_id=user.id,
            ),
        )
        await session.commit()

    async def change_password(
        self,
        session: AsyncSession,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change an authenticated user's password and revoke all sessions."""
        user = await self._user_repository.get_by_for_update(
            session=session,
            id=user_id,
        )
        if user is None:
            raise UserNotFoundError
        if not verify_password(
            password=current_password,
            hashed=user.hashed_password,
        ):
            raise CurrentPasswordError
        if verify_password(password=new_password, hashed=user.hashed_password):
            raise PasswordUnchangedError
        now = datetime.now(tz=UTC)
        user.hashed_password = hash_password(new_password)
        await self._session_repository.revoke_all_for_user(
            session=session,
            user_id=user.id,
            revoked_at=now,
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user.id,
                action="user.password_change",
                entity_type="user",
                entity_id=user.id,
            ),
        )
        await session.commit()

    async def _issue_action_token(
        self,
        session: AsyncSession,
        user_id: int,
        purpose: AuthActionPurpose,
        expires_delta: timedelta,
    ) -> str:
        """Replace an older link with a fresh opaque one-time token."""
        user = await self._user_repository.get_by_for_update(
            session=session,
            id=user_id,
        )
        if user is None:
            raise UserNotFoundError
        await self._action_token_repository.delete_all(
            session=session,
            user_id=user_id,
            purpose=purpose.value,
        )
        token = secrets.token_urlsafe(48)
        await self._action_token_repository.create(
            session=session,
            data={
                "user_id": user_id,
                "purpose": purpose.value,
                "token_hash": self._hash_action_token(token),
                "expires_at": datetime.now(tz=UTC) + expires_delta,
            },
        )
        return token

    async def _get_valid_action_token(
        self,
        session: AsyncSession,
        token: str,
        purpose: AuthActionPurpose,
    ) -> AuthActionToken:
        """Lock and validate an unconsumed account action token."""
        action_token = await self._action_token_repository.get_by_hash_for_update(
            session=session,
            token_hash=self._hash_action_token(token),
        )
        if (
            action_token is None
            or action_token.purpose != purpose.value
            or action_token.used_at is not None
            or action_token.expires_at <= datetime.now(tz=UTC)
        ):
            raise AuthActionTokenError
        return action_token

    async def _send_verification(self, email: str, token: str) -> None:
        """Deliver a verification email without rolling back durable signup."""
        try:
            await self._email_sender.send_verification(email, token)
        except EmailConnectionError:
            logger.exception("Unable to deliver email verification link")

    async def _send_password_reset(self, email: str, token: str) -> None:
        """Deliver a recovery email while preserving a generic API response."""
        try:
            await self._email_sender.send_password_reset(email, token)
        except EmailConnectionError:
            logger.exception("Unable to deliver password reset link")

    def _login_response(self, email: str, auth_session_id: int) -> LoginResponse:
        """Build a short-lived access-token response."""
        return LoginResponse(
            access_token=self._create_access_token(
                data={"sub": email, "sid": auth_session_id}
            ),
            token_type=auth_settings.token_type,
        )

    @staticmethod
    def _new_refresh_token() -> str:
        """Generate an opaque high-entropy refresh token."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        """Hash a refresh token before database lookup/storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _hash_action_token(token: str) -> str:
        """Hash an account action token before database lookup/storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def register(
        self,
        session: AsyncSession,
        data: UserCreate,
    ) -> UserResponse:
        """Register a user.

        Args:
            session: The session.
            data: User create.

        Returns:
            The user.

        Raises:
            UserAlreadyExistsError: If the user already exists.

        """
        if await self._user_repository.get_by(session=session, email=data.email):
            raise UserAlreadyExistsError

        user = await self._user_repository.create(
            session=session,
            data={
                "email": data.email,
                "hashed_password": hash_password(password=data.password),
                "email_verified_at": None,
            },
        )

        await self._llm_provider_repository.create(
            session=session,
            data={
                "user_id": user.id,
                "name": LLMProviderType.OLLAMA.value,
                "type": LLMProviderType.OLLAMA,
                "config": {},
                "base_url": ollama_settings.url,
            },
        )

        verification_token = await self._issue_action_token(
            session=session,
            user_id=user.id,
            purpose=AuthActionPurpose.VERIFY_EMAIL,
            expires_delta=timedelta(
                hours=auth_email_settings.verification_expire_hours
            ),
        )
        await session.commit()
        await self._send_verification(user.email, verification_token)
        return UserResponse.model_validate(user)
