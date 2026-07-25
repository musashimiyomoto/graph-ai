"""Repositories for unified connections and OAuth states."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Connection, ConnectionOAuthState
from db.repositories.base import BaseRepository


class ConnectionRepository(BaseRepository[Connection]):
    """Data access for tenant-owned connections."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=Connection)

    async def get_for_update(
        self, *, session: AsyncSession, connection_id: int
    ) -> Connection | None:
        """Lock one connection while credentials are refreshed or revoked."""
        result = await session.execute(
            select(Connection).where(Connection.id == connection_id).with_for_update()
        )
        return result.scalar_one_or_none()


class ConnectionOAuthStateRepository(BaseRepository[ConnectionOAuthState]):
    """Data access for single-use OAuth states."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=ConnectionOAuthState)

    async def get_by_hash_for_update(
        self, *, session: AsyncSession, state_hash: str
    ) -> ConnectionOAuthState | None:
        """Lock a state so a callback can consume it exactly once."""
        result = await session.execute(
            select(ConnectionOAuthState)
            .where(ConnectionOAuthState.state_hash == state_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def delete_expired(self, *, session: AsyncSession, now: datetime) -> None:
        """Delete expired OAuth states during bounded flow creation."""
        await session.execute(
            delete(ConnectionOAuthState).where(ConnectionOAuthState.expires_at <= now)
        )
        await session.flush()
