"""Narrow access boundary for encrypted reusable connection credentials."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Connection
from db.repositories import ConnectionRepository
from enums import ConnectionAuthType, ConnectionStatus
from utils.encryption import decrypt, encrypt


def seal_credentials(payload: dict[str, Any]) -> str:
    """Serialize and encrypt one credential envelope."""
    return encrypt(json.dumps(payload))


def open_credentials(connection: Connection) -> dict[str, Any]:
    """Decrypt and validate one stored credential envelope."""
    payload = json.loads(decrypt(connection.credentials))
    if not isinstance(payload, dict):
        message = "Connection credential envelope must contain an object"
        raise TypeError(message)
    return payload


def connection_secret(connection: Connection) -> str | None:
    """Return the connection's opaque primary secret, when configured."""
    secret = open_credentials(connection).get("secret")
    return secret if isinstance(secret, str) and secret else None


async def create_profile_connection(
    *,
    session: AsyncSession,
    user_id: int,
    name: str,
    provider: str,
    secret: str | None,
) -> Connection:
    """Create the sole credential record backing one provider profile."""
    return await ConnectionRepository().create(
        session=session,
        data={
            "user_id": user_id,
            "name": name,
            "provider": provider,
            "auth_type": (
                ConnectionAuthType.API_KEY
                if secret is not None
                else ConnectionAuthType.NONE
            ),
            "status": ConnectionStatus.ACTIVE,
            "config": {},
            "scopes": [],
            "credentials": seal_credentials(
                {"secret": secret} if secret is not None else {}
            ),
        },
    )


async def get_profile_connection(
    *, session: AsyncSession, connection_id: int, user_id: int
) -> Connection | None:
    """Load an owned reusable connection used by a provider profile."""
    return await ConnectionRepository().get_by(
        session=session, id=connection_id, user_id=user_id
    )


async def update_profile_connection(  # noqa: PLR0913
    *,
    session: AsyncSession,
    connection_id: int,
    name: str | None = None,
    provider: str | None = None,
    secret: str | None = None,
    replace_secret: bool = False,
) -> Connection | None:
    """Update profile identity and optionally replace its primary secret."""
    data: dict[str, Any] = {}
    if name is not None:
        data["name"] = name
    if provider is not None:
        data["provider"] = provider
    if replace_secret:
        data.update(
            auth_type=(
                ConnectionAuthType.API_KEY
                if secret is not None
                else ConnectionAuthType.NONE
            ),
            credentials=seal_credentials(
                {"secret": secret} if secret is not None else {}
            ),
        )
    if not data:
        return await ConnectionRepository().get_by(session=session, id=connection_id)
    return await ConnectionRepository().update_by(
        session=session, id=connection_id, data=data
    )
