"""Saved PostgreSQL connection business logic."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from credentials import create_profile_connection
from db.repositories import ConnectionRepository, PostgresConnectionRepository
from exceptions import (
    BlockedURLError,
    PostgresConnectionAlreadyExistsError,
    PostgresConnectionNotFoundError,
)
from schemas import PostgresConnectionCreate, PostgresConnectionResponse
from usecases.audit import AuditEvent, AuditUsecase
from utils.network import blocked_postgres_dsn_reason


class PostgresConnectionUsecase:
    """CRUD for encrypted PostgreSQL connections."""

    def __init__(self) -> None:
        """Initialize dependencies."""
        self._repository = PostgresConnectionRepository()
        self._audit_usecase = AuditUsecase()

    async def create_connection(
        self, session: AsyncSession, user_id: int, data: PostgresConnectionCreate
    ) -> PostgresConnectionResponse:
        """Create and encrypt a PostgreSQL connection."""
        reason = await blocked_postgres_dsn_reason(data.dsn)
        if reason is not None:
            raise BlockedURLError(message=reason)
        try:
            connection = await create_profile_connection(
                session=session,
                user_id=user_id,
                name=data.name,
                provider="postgres",
                secret=data.dsn,
            )
            created = await self._repository.create(
                session=session,
                data={
                    "user_id": user_id,
                    "name": data.name,
                    "connection_id": connection.id,
                },
            )
        except IntegrityError as exc:
            await session.rollback()
            raise PostgresConnectionAlreadyExistsError from exc
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="postgres_connection.create",
                entity_type="postgres_connection",
                entity_id=created.id,
                metadata={"name": created.name},
            ),
        )
        await session.commit()
        return PostgresConnectionResponse.model_validate(created)

    async def list_connections(
        self, session: AsyncSession, user_id: int
    ) -> list[PostgresConnectionResponse]:
        """List connection metadata for the current account."""
        return [
            PostgresConnectionResponse.model_validate(item)
            for item in await self._repository.get_all(session=session, user_id=user_id)
        ]

    async def delete_connection(
        self, session: AsyncSession, user_id: int, connection_id: int
    ) -> None:
        """Delete an owned PostgreSQL connection."""
        profile = await self._repository.get_by(
            session=session, id=connection_id, user_id=user_id
        )
        if profile is None:
            raise PostgresConnectionNotFoundError
        await ConnectionRepository().delete_by(
            session=session, id=profile.connection_id, user_id=user_id
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="postgres_connection.delete",
                entity_type="postgres_connection",
                entity_id=connection_id,
            ),
        )
        await session.commit()
