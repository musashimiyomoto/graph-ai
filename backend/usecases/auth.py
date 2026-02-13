"""Auth use case implementation."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import LLMProviderRepository, UserRepository
from enums import LLMProviderType
from exceptions import (
    AuthCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from schemas import LoginCreate, LoginResponse, UserCreate, UserResponse
from settings import auth_settings, ollama_settings
from utils.crypto import hash_password, verify_password


class AuthUsecase:
    """Auth business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._user_repository = UserRepository()
        self._llm_provider_repository = LLMProviderRepository()

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
        email = self.get_payload(token=token).get("sub")

        if email is None:
            raise AuthCredentialsError

        user = await self._user_repository.get_by(session=session, email=email)

        if not user:
            raise AuthCredentialsError

        return UserResponse.model_validate(user)

    async def login(self, session: AsyncSession, data: LoginCreate) -> LoginResponse:
        """Login a user.

        Args:
            session: The session.
            data: Login data.

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

        return LoginResponse(
            access_token=self._create_access_token(
                data={"sub": user.email},
                expires_delta=timedelta(
                    minutes=auth_settings.access_token_expire_minutes
                ),
            ),
            token_type=auth_settings.token_type,
        )

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

        return UserResponse.model_validate(user)
