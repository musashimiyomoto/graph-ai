"""Redis-backed per-tenant execution quota pre-check."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from api.dependencies.auth import get_current_user
from api.dependencies.redis import get_redis_client
from exceptions import QuotaExceededError
from schemas import UserResponse
from settings import quota_settings


def _execution_quota_key(user_id: int) -> str:
    """Build the per-user, per-day execution-count counter key."""
    day = datetime.now(tz=UTC).strftime("%Y%m%d")
    return f"quota:executions:{user_id}:{day}"


async def enforce_execution_quota(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> None:
    """Reject a new execution when the tenant is over its daily execution quota.

    A cheap Redis fixed-window counter keyed by ``(user, day)`` — the fast path
    that avoids a DB round-trip on the hot ``POST /executions`` route. The
    durable check in ``UsageUsecase.check_quota`` remains the authority (and
    also covers Telegram/schedule triggers that never hit this dependency), so
    a lost/reset Redis counter can never let a tenant exceed the limit for
    long. Skipped entirely when no execution limit is configured.

    Raises:
        QuotaExceededError: If the tenant is at or over the daily limit.

    """
    max_executions = quota_settings.max_executions_per_day
    if max_executions <= 0:
        return

    key = _execution_quota_key(current_user.id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, quota_settings.window_seconds)
    if count > max_executions:
        raise QuotaExceededError(
            message="Daily execution quota exceeded. Please try again tomorrow."
        )
