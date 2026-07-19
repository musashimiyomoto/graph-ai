"""Authentication action token model factory."""

import hashlib
from datetime import UTC, datetime, timedelta

from factory.declarations import LazyAttribute, LazyFunction

from db.models import AuthActionToken
from enums import AuthActionPurpose
from tests.factories.base import AsyncSQLAlchemyModelFactory


class AuthActionTokenFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating hashed one-time account action tokens."""

    class Meta:
        """Factory configuration."""

        model = AuthActionToken

    purpose = AuthActionPurpose.VERIFY_EMAIL.value
    token_hash = LazyAttribute(
        lambda obj: hashlib.sha256(f"token-{obj.user_id}".encode()).hexdigest()
    )
    expires_at = LazyFunction(lambda: datetime.now(tz=UTC) + timedelta(hours=1))
