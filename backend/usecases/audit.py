"""Audit log use case implementation."""

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.pagination import Pagination
from db.repositories import AuditLogRepository
from schemas import AuditLogResponse


@dataclass(frozen=True)
class AuditEvent:
    """One tenant-visible mutating action to record in the audit trail."""

    user_id: int
    action: str
    entity_type: str
    entity_id: int | None = None
    metadata: dict = field(default_factory=dict)


class AuditUsecase:
    """Audit trail business logic.

    ``record`` stages an audit row on the caller's session without committing,
    so it participates in the same transaction as the mutation it describes —
    the caller commits both together. ``get_audit_logs`` reads a tenant's
    trail newest-first for the usage API.
    """

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._audit_log_repository = AuditLogRepository()

    async def record(self, session: AsyncSession, event: AuditEvent) -> None:
        """Stage an audit row (flushed, not committed).

        Args:
            session: The session (committed by the caller).
            event: The action to record.

        """
        await self._audit_log_repository.create(
            session=session,
            data={
                "user_id": event.user_id,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "audit_metadata": event.metadata,
            },
        )

    async def get_audit_logs(
        self, session: AsyncSession, user_id: int, pagination: Pagination
    ) -> list[AuditLogResponse]:
        """List a tenant's audit trail, newest first.

        Args:
            session: The session.
            user_id: The tenant.
            pagination: Limit/offset.

        Returns:
            The audit log rows.

        """
        rows = await self._audit_log_repository.get_all(
            session=session,
            user_id=user_id,
            limit=pagination.limit,
            offset=pagination.offset,
            descending=True,
        )
        return [AuditLogResponse.model_validate(row) for row in rows]
