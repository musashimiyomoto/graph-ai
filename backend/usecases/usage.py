"""Usage and quota use case implementation."""

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import UsageRecordRepository
from exceptions import QuotaExceededError
from schemas import QuotaStatus, UsageSummaryResponse
from settings import quota_settings


def _current_period() -> date:
    """Return the current UTC usage window (calendar day)."""
    return datetime.now(tz=UTC).date()


def _remaining(limit: int, used: int) -> int | None:
    """Compute remaining allowance for a dimension (None when unlimited)."""
    if limit <= 0:
        return None
    return max(0, limit - used)


class UsageUsecase:
    """Per-tenant usage recording, quota checks, and summaries.

    The DB ``usage_records`` row is the authority; the Redis counter (see
    ``api/dependencies/quota.py``) is only a cheap fast-path pre-check. This
    usecase enforces the same limits against the durable record so a trigger
    that bypasses the HTTP dependency (Telegram/schedule) is still bounded.
    """

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._usage_record_repository = UsageRecordRepository()

    async def check_quota(self, session: AsyncSession, user_id: int) -> None:
        """Reject if the user is already at or over a configured daily limit.

        Args:
            session: The session.
            user_id: The tenant to check.

        Raises:
            QuotaExceededError: If a configured limit is already reached.

        """
        if not quota_settings.enabled:
            return

        record = await self._usage_record_repository.get_for_period(
            session=session, user_id=user_id, period_start=_current_period()
        )
        executions_used = record.executions_count if record else 0
        tokens_used = record.total_tokens if record else 0

        max_executions = quota_settings.max_executions_per_day
        if max_executions > 0 and executions_used >= max_executions:
            raise QuotaExceededError(
                message="Daily execution quota exceeded. Please try again tomorrow."
            )

        max_tokens = quota_settings.max_tokens_per_day
        if max_tokens > 0 and tokens_used >= max_tokens:
            raise QuotaExceededError(
                message="Daily token quota exceeded. Please try again tomorrow."
            )

    async def record_run(
        self,
        session: AsyncSession,
        user_id: int,
        total_tokens: int,
    ) -> None:
        """Record one finalized execution and its token cost (flushed, not committed).

        Args:
            session: The session (committed by the caller).
            user_id: The tenant that ran the execution.
            total_tokens: Tokens the run consumed.

        """
        await self._usage_record_repository.increment(
            session=session,
            user_id=user_id,
            period_start=_current_period(),
            executions_delta=1,
            tokens_delta=total_tokens,
        )

    async def get_summary(
        self, session: AsyncSession, user_id: int
    ) -> UsageSummaryResponse:
        """Build the current window's usage summary for a tenant.

        Args:
            session: The session.
            user_id: The tenant.

        Returns:
            The usage summary with per-dimension limit/used/remaining.

        """
        period = _current_period()
        record = await self._usage_record_repository.get_for_period(
            session=session, user_id=user_id, period_start=period
        )
        executions_used = record.executions_count if record else 0
        tokens_used = record.total_tokens if record else 0

        max_executions = quota_settings.max_executions_per_day
        max_tokens = quota_settings.max_tokens_per_day
        return UsageSummaryResponse(
            period_start=period,
            executions=QuotaStatus(
                limit=max_executions,
                used=executions_used,
                remaining=_remaining(max_executions, executions_used),
            ),
            tokens=QuotaStatus(
                limit=max_tokens,
                used=tokens_used,
                remaining=_remaining(max_tokens, tokens_used),
            ),
        )
