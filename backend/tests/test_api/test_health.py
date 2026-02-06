"""Health endpoint tests."""

import pytest

from tests.test_api.base import BaseTestCase


class TestHealthLiveness(BaseTestCase):
    """Liveness checks for the health endpoint."""

    url = "/health/liveness"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Returns a healthy status for liveness checks."""
        response = await self.client.get(url=self.url)

        data = await self.assert_response_ok(response=response)
        if data.get("status") is not True:
            pytest.fail("Expected liveness status to be true")


class TestHealthReadiness(BaseTestCase):
    """Readiness checks for the health endpoint."""

    url = "/health/readiness"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Returns expected fields and types for readiness checks."""
        response = await self.client.get(url=self.url)

        data = await self.assert_response_ok(response=response)
        self.assert_has_keys(data, {"services", "status"})
        if not isinstance(data["services"], list):
            pytest.fail("Expected services to be a list")
        if not isinstance(data["status"], bool):
            pytest.fail("Expected status to be a boolean")
