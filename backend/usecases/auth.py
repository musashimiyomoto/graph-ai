"""Auth use case implementation."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import (
    AuthSessionRepository,
    LLMProviderRepository,
    UserRepository,
)
from enums import LLMProviderType
from exceptions import (
    AuthCredentialsError,
    AuthSessionNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from schemas import (
    AuthSessionResponse,
    LoginCreate,
    LoginResponse,
    UserCreate,
    UserResponse,
)
from settings import auth_settings, ollama_settings
from utils.crypto import hash_password, verify_password


class AuthUsecase:
    """Auth business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._user_repository = UserRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._session_repository = AuthSessionRepository()

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

        await session.commit()
        return UserResponse.model_validate(user)
