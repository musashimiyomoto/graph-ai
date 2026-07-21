"""Rate limiting tests (real Redis) for the auth endpoints."""

from collections.abc import AsyncGenerator
from http import HTTPStatus

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from api.dependencies import rate_limit
from api.dependencies import redis as redis_dependency
from main import app
from tests.test_api.base import BaseTestCase

_LOGIN_MAX_ATTEMPTS = 10
_REGISTER_MAX_ATTEMPTS = 5


class TestAuthRateLimit(BaseTestCase):
    """Tests for the Redis-backed rate limiter on login/register."""

    @pytest_asyncio.fixture
    async def real_redis_rate_limit(
        self, test_redis: Redis
    ) -> AsyncGenerator[None, None]:
        """Swap the test-suite's no-op rate limit override for a real one."""
        previous_login = app.dependency_overrides.pop(
            rate_limit.enforce_login_rate_limit, None
        )
        previous_register = app.dependency_overrides.pop(
            rate_limit.enforce_register_rate_limit, None
        )
        app.dependency_overrides[redis_dependency.get_redis_client] = lambda: test_redis
        try:
            yield
        finally:
            app.dependency_overrides.pop(redis_dependency.get_redis_client, None)
            if previous_login is not None:
                app.dependency_overrides[rate_limit.enforce_login_rate_limit] = (
                    previous_login
                )
            if previous_register is not None:
                app.dependency_overrides[rate_limit.enforce_register_rate_limit] = (
                    previous_register
                )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("real_redis_rate_limit")
    async def test_login_blocks_after_threshold(self) -> None:
        """Repeated login attempts from the same client eventually 429."""
        payload = {"email": "nobody@example.com", "password": "wrong-password"}

        statuses = []
        for _ in range(_LOGIN_MAX_ATTEMPTS + 1):
            response = await self.client.post(url="/auth/login", json=payload)
            statuses.append(response.status_code)

        if statuses[-1] != HTTPStatus.TOO_MANY_REQUESTS:
            message = (
                f"Expected the final login attempt to be rate-limited, got {statuses}"
            )
            pytest.fail(message)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("real_redis_rate_limit")
    async def test_register_blocks_after_threshold(self) -> None:
        """Repeated registration attempts from the same client eventually 429."""
        statuses = []
        for index in range(_REGISTER_MAX_ATTEMPTS + 1):
            response = await self.client.post(
                url="/auth/register",
                json={
                    "email": f"rate-limit-{index}@example.com",
                    "password": "a-long-enough-password",
                },
            )
            statuses.append(response.status_code)

        if statuses[-1] != HTTPStatus.TOO_MANY_REQUESTS:
            message = (
                f"Expected the final register attempt to be rate-limited: {statuses}"
            )
            pytest.fail(message)
