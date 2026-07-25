"""Typed durable state business logic."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import (
    ExecutionRepository,
    StateEntryHistoryRepository,
    StateEntryRepository,
    WorkflowRepository,
)
from enums import StateHistoryOperation, StateScope
from exceptions import (
    ExecutionNotFoundError,
    StateEntryNotFoundError,
    StateScopeUnavailableError,
    StateVersionConflictError,
)
from schemas import (
    StateEntryResponse,
    StateHistoryResponse,
    StateMutation,
    TriggerEvent,
)
from usecases.audit import AuditEvent, AuditUsecase

if TYPE_CHECKING:
    from db.models import Execution, StateEntry


@dataclass(frozen=True)
class _ResolvedScope:
    """Authorized workflow and concrete reference for one state scope."""

    execution: "Execution"
    workflow_id: int
    scope: StateScope
    scope_ref: str


@dataclass(frozen=True)
class StateAccess:
    """Authenticated execution context and requested scoped state key."""

    user_id: int
    execution_id: int
    scope: StateScope
    key: str


class StateUsecase:
    """Read and mutate typed state through an execution identity context."""

    def __init__(self) -> None:
        """Initialize repositories and audit orchestration."""
        self._execution_repository = ExecutionRepository()
        self._workflow_repository = WorkflowRepository()
        self._state_repository = StateEntryRepository()
        self._history_repository = StateEntryHistoryRepository()
        self._audit_usecase = AuditUsecase()

    async def get(
        self,
        *,
        session: AsyncSession,
        access: StateAccess,
    ) -> StateEntryResponse:
        """Return a current state value, treating expired values as absent."""
        resolved = await self._resolve_scope(
            session=session,
            user_id=access.user_id,
            execution_id=access.execution_id,
            scope=access.scope,
        )
        entry = await self._state_repository.get_by(
            session=session,
            workflow_id=resolved.workflow_id,
            scope=access.scope,
            scope_ref=resolved.scope_ref,
            key=access.key,
        )
        if entry is None or self._is_expired(entry):
            raise StateEntryNotFoundError
        return StateEntryResponse.model_validate(entry)

    async def set(
        self,
        *,
        session: AsyncSession,
        access: StateAccess,
        mutation: StateMutation,
    ) -> StateEntryResponse:
        """Create or replace a state value with compare-and-set semantics."""
        resolved = await self._resolve_scope(
            session=session,
            user_id=access.user_id,
            execution_id=access.execution_id,
            scope=access.scope,
        )
        await self._lock_state_key(
            session=session,
            resolved=resolved,
            key=access.key,
        )
        entry = await self._state_repository.get_for_update(
            session=session,
            workflow_id=resolved.workflow_id,
            scope=access.scope,
            scope_ref=resolved.scope_ref,
            key=access.key,
        )
        active = entry is not None and not self._is_expired(entry)
        self._check_expected_version(
            expected=mutation.expected_version,
            entry=entry if active else None,
        )
        expires_at = (
            datetime.now(tz=UTC) + timedelta(seconds=mutation.ttl_seconds)
            if mutation.ttl_seconds is not None
            else None
        )
        value = mutation.value.model_dump(mode="json")
        operation = (
            StateHistoryOperation.UPDATE if active else StateHistoryOperation.CREATE
        )
        if entry is None:
            entry = await self._state_repository.create(
                session=session,
                data={
                    "owner_id": access.user_id,
                    "workflow_id": resolved.workflow_id,
                    "scope": access.scope,
                    "scope_ref": resolved.scope_ref,
                    "key": access.key,
                    "value": value,
                    "version": 1,
                    "expires_at": expires_at,
                },
            )
        else:
            updated = await self._state_repository.update_by(
                session=session,
                data={
                    "value": value,
                    "version": entry.version + 1,
                    "expires_at": expires_at,
                },
                id=entry.id,
            )
            if updated is None:
                message = "Locked state entry disappeared during update"
                raise RuntimeError(message)
            entry = updated
        await self._record_history(
            session=session,
            resolved=resolved,
            entry=entry,
            operation=operation,
            value=value,
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=access.user_id,
                action=f"state.{operation.value}",
                entity_type="state_entry",
                entity_id=entry.id,
                metadata={
                    "workflow_id": resolved.workflow_id,
                    "execution_id": access.execution_id,
                    "scope": access.scope.value,
                    "key": access.key,
                    "version": entry.version,
                },
            ),
        )
        await session.commit()
        return StateEntryResponse.model_validate(entry)

    async def delete(
        self,
        *,
        session: AsyncSession,
        access: StateAccess,
        expected_version: int | None,
    ) -> None:
        """Delete a current state value and retain its append-only history."""
        resolved = await self._resolve_scope(
            session=session,
            user_id=access.user_id,
            execution_id=access.execution_id,
            scope=access.scope,
        )
        entry = await self._state_repository.get_for_update(
            session=session,
            workflow_id=resolved.workflow_id,
            scope=access.scope,
            scope_ref=resolved.scope_ref,
            key=access.key,
        )
        if entry is None or self._is_expired(entry):
            raise StateEntryNotFoundError
        self._check_expected_version(expected=expected_version, entry=entry)
        entry_id = entry.id
        await self._record_history(
            session=session,
            resolved=resolved,
            entry=entry,
            operation=StateHistoryOperation.DELETE,
            value=entry.value,
        )
        await self._state_repository.delete_by(session=session, id=entry.id)
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=access.user_id,
                action="state.delete",
                entity_type="state_entry",
                entity_id=entry_id,
                metadata={
                    "workflow_id": resolved.workflow_id,
                    "execution_id": access.execution_id,
                    "scope": access.scope.value,
                    "key": access.key,
                    "version": entry.version,
                },
            ),
        )
        await session.commit()

    async def history(
        self,
        *,
        session: AsyncSession,
        access: StateAccess,
        limit: int,
        offset: int,
    ) -> list[StateHistoryResponse]:
        """Return newest-first append-only history for one scoped key."""
        resolved = await self._resolve_scope(
            session=session,
            user_id=access.user_id,
            execution_id=access.execution_id,
            scope=access.scope,
        )
        rows = await self._history_repository.get_all(
            session=session,
            owner_id=access.user_id,
            workflow_id=resolved.workflow_id,
            scope=access.scope,
            scope_ref=resolved.scope_ref,
            key=access.key,
            limit=limit,
            offset=offset,
            descending=True,
        )
        return [StateHistoryResponse.model_validate(row) for row in rows]

    async def _resolve_scope(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        execution_id: int,
        scope: StateScope,
    ) -> _ResolvedScope:
        """Authorize the execution and derive the selected stable scope key."""
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if execution is None:
            raise ExecutionNotFoundError
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=execution.workflow_id,
            owner_id=user_id,
        )
        if workflow is None:
            raise ExecutionNotFoundError

        if scope is StateScope.EXECUTION:
            scope_ref = str(execution.id)
        elif scope is StateScope.WORKFLOW:
            scope_ref = str(execution.workflow_id)
        elif scope is StateScope.CONVERSATION:
            if execution.conversation_id is None:
                raise StateScopeUnavailableError(
                    message="Execution has no conversation state scope"
                )
            scope_ref = str(execution.conversation_id)
        else:
            event = TriggerEvent.model_validate(execution.trigger_event)
            actor = event.sender
            actor_ref = (actor.id or actor.address) if actor else None
            if not actor_ref:
                raise StateScopeUnavailableError(
                    message="Execution has no sender identity for user state"
                )
            scope_ref = f"{event.channel.value}:{actor_ref}"
        return _ResolvedScope(
            execution=execution,
            workflow_id=execution.workflow_id,
            scope=scope,
            scope_ref=scope_ref,
        )

    @staticmethod
    async def _lock_state_key(
        *, session: AsyncSession, resolved: _ResolvedScope, key: str
    ) -> None:
        """Serialize create-or-update races even while a key has no row to lock."""
        material = (
            f"state:{resolved.workflow_id}:{resolved.scope.value}:"
            f"{resolved.scope_ref}:{key}"
        ).encode()
        lock_key = int.from_bytes(
            hashlib.sha256(material).digest()[:8],
            byteorder="big",
            signed=True,
        )
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    @staticmethod
    def _is_expired(entry: "StateEntry") -> bool:
        """Return whether an entry's TTL has elapsed."""
        return entry.expires_at is not None and entry.expires_at <= datetime.now(tz=UTC)

    @staticmethod
    def _check_expected_version(
        *, expected: int | None, entry: "StateEntry | None"
    ) -> None:
        """Enforce optional create-only or exact-version compare-and-set."""
        if expected is None:
            return
        if expected == 0:
            if entry is not None:
                raise StateVersionConflictError
            return
        if entry is None or entry.version != expected:
            raise StateVersionConflictError

    async def _record_history(
        self,
        *,
        session: AsyncSession,
        resolved: _ResolvedScope,
        entry: "StateEntry",
        operation: StateHistoryOperation,
        value: dict,
    ) -> None:
        """Append one immutable state mutation record."""
        await self._history_repository.create(
            session=session,
            data={
                "state_entry_id": entry.id,
                "owner_id": entry.owner_id,
                "workflow_id": resolved.workflow_id,
                "execution_id": resolved.execution.id,
                "scope": resolved.scope,
                "scope_ref": resolved.scope_ref,
                "key": entry.key,
                "operation": operation.value,
                "value": value,
                "version": entry.version,
                "expires_at": entry.expires_at,
            },
        )
