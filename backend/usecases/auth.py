"""Auth use case implementation."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import (
    AuthCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from models import User
from repositories import UserRepository
from settings import auth_settings
from utils.crypto import hash_password, verify_password


class AuthUsecase:
    """Auth business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._user_repository = UserRepository()

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

        if expires_delta:
            expire = datetime.now(tz=UTC) + expires_delta
        else:
            expire = datetime.now(tz=UTC) + timedelta(
                minutes=auth_settings.access_token_expire_minutes
            )

        to_encode.update({"exp": expire})

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
    ) -> User:
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

        return user

    async def _get_user_by_email(self, session: AsyncSession, email: str) -> User:
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

        return user

    async def get_current_user(
        self,
        session: AsyncSession,
        token: str,
    ) -> User:
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
        email = payload.get("sub")

        if email is None:
            raise AuthCredentialsError

        user = await self._user_repository.get_by(session=session, email=email)

        if not user:
            raise AuthCredentialsError

        return user

    async def login(self, session: AsyncSession, email: str, password: str) -> str:
        """Login a user.

        Args:
            session: The session.
            email: The email.
            password: The password.

        Returns:
            The token.

        Raises:
            AuthCredentialsError: If the user is not authenticated.

        """
        user = await self._authenticate(
            session=session,
            email=email,
            password=password,
        )

        if not user:
            raise AuthCredentialsError

        return self._create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=auth_settings.access_token_expire_minutes),
        )

    async def register(
        self,
        session: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Register a user.

        Args:
            session: The session.
            email: The email.
            password: The password.

        Returns:
            The user.

        Raises:
            UserAlreadyExistsError: If the user already exists.

        """
        if await self._user_repository.get_by(session=session, email=email):
            raise UserAlreadyExistsError

        return await self._user_repository.create(
            session=session,
            data={"email": email, "hashed_password": hash_password(password=password)},
        )
