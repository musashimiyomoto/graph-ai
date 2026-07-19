"""Redis-backed rate limiting for sensitive endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from api.dependencies.redis import get_redis_client
from exceptions import RateLimitExceededError

_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 60
_REGISTER_MAX_ATTEMPTS = 5
_REGISTER_WINDOW_SECONDS = 60
_EMAIL_ACTION_MAX_ATTEMPTS = 5
_EMAIL_ACTION_WINDOW_SECONDS = 60


def _client_ip(request: Request) -> str:
    """Return the connecting client's IP address, or 'unknown' if absent."""
    return request.client.host if request.client else "unknown"


async def _enforce(
    redis: Redis,
    key: str,
    *,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Increment a fixed-window request counter and enforce its limit.

    Args:
        redis: The Redis client.
        key: The counter key, scoped to an endpoint and client.
        max_attempts: How many requests are allowed within the window.
        window_seconds: The window length, started on the first request.

    Raises:
        RateLimitExceededError: If the counter exceeds ``max_attempts``.

    """
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > max_attempts:
        raise RateLimitExceededError


async def enforce_login_rate_limit(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> None:
    """Rate-limit login attempts per client IP."""
    await _enforce(
        redis,
        f"ratelimit:login:{_client_ip(request)}",
        max_attempts=_LOGIN_MAX_ATTEMPTS,
        window_seconds=_LOGIN_WINDOW_SECONDS,
    )


async def enforce_register_rate_limit(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> None:
    """Rate-limit registration attempts per client IP."""
    await _enforce(
        redis,
        f"ratelimit:register:{_client_ip(request)}",
        max_attempts=_REGISTER_MAX_ATTEMPTS,
        window_seconds=_REGISTER_WINDOW_SECONDS,
    )


async def enforce_email_action_rate_limit(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> None:
    """Rate-limit verification and recovery email requests per client IP."""
    await _enforce(
        redis,
        f"ratelimit:email-action:{_client_ip(request)}",
        max_attempts=_EMAIL_ACTION_MAX_ATTEMPTS,
        window_seconds=_EMAIL_ACTION_WINDOW_SECONDS,
    )
