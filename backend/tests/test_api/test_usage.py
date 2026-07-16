"""Usage, audit, and metrics API tests."""

import uuid
from http import HTTPStatus

import pytest

from exceptions import QuotaExceededError
from settings import quota_settings
from tests.factories import UserFactory
from tests.test_api.base import BaseTestCase
from usecases import UsageUsecase


class TestUsageSummary(BaseTestCase):
    """Tests for GET /usage."""

    url = "/usage"

    @pytest.mark.asyncio
    async def test_requires_auth(self) -> None:
        """An unauthenticated request is rejected."""
        response = await self.client.get(url=self.url)
        if response.status_code not in {
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        }:
            pytest.fail(f"Expected 401/403, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_reports_zero_usage_for_new_user(self) -> None:
        """A fresh user's summary shows zero executions and tokens used."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"period_start", "executions", "tokens"})
        if data["executions"]["used"] != 0 or data["tokens"]["used"] != 0:
            pytest.fail("A new user should have zero recorded usage")


class TestAuditLog(BaseTestCase):
    """Tests for GET /usage/audit."""

    url = "/usage/audit"

    @pytest.mark.asyncio
    async def test_records_workflow_create(self) -> None:
        """Creating a workflow appends a workflow.create audit row."""
        _, headers = await self.create_user_and_get_token()

        create = await self.client.post(
            url="/workflows",
            json={"name": f"workflow-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        workflow = await self.assert_response_dict(response=create)

        response = await self.client.get(url=self.url, headers=headers)

        rows = await self.assert_response_list(response=response)
        actions = {row["action"] for row in rows}
        if "workflow.create" not in actions:
            pytest.fail("Expected a workflow.create audit row")
        matching = next(
            row for row in rows if row["action"] == "workflow.create"
        )
        if matching["entity_id"] != workflow["id"]:
            pytest.fail("Audit row entity_id did not match the created workflow")

    @pytest.mark.asyncio
    async def test_scoped_to_current_user(self) -> None:
        """A user only sees their own audit trail."""
        _, headers_a = await self.create_user_and_get_token()
        _, headers_b = await self.create_user_and_get_token()

        await self.client.post(
            url="/workflows",
            json={"name": f"workflow-{uuid.uuid4().hex[:8]}"},
            headers=headers_a,
        )

        response = await self.client.get(url=self.url, headers=headers_b)

        rows = await self.assert_response_list(response=response)
        if rows:
            pytest.fail("A different user's audit trail must not leak")


class TestMetricsEndpoint(BaseTestCase):
    """Tests for GET /metrics."""

    @pytest.mark.asyncio
    async def test_exposes_prometheus_text(self) -> None:
        """The metrics endpoint is reachable and unauthenticated."""
        response = await self.client.get(url="/metrics")

        if response.status_code != HTTPStatus.OK:
            pytest.fail(f"Expected 200 from /metrics, got {response.status_code}")
        if "graphai_" not in response.text:
            pytest.fail("Metrics output should contain graphai_ series")


class TestQuotaEnforcement(BaseTestCase):
    """Tests for the durable quota check in UsageUsecase."""

    @pytest.mark.asyncio
    async def test_check_quota_rejects_over_execution_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A user at the daily execution limit is rejected by check_quota."""
        monkeypatch.setattr(quota_settings, "max_executions_per_day", 1)

        user = await UserFactory.create_async(
            session=self.session,
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        )
        usecase = UsageUsecase()

        # First run is under the limit and records usage.
        await usecase.check_quota(session=self.session, user_id=user.id)
        await usecase.record_run(
            session=self.session, user_id=user.id, total_tokens=0
        )
        await self.session.commit()

        # Second attempt is now at the limit and must be rejected.
        with pytest.raises(QuotaExceededError):
            await usecase.check_quota(session=self.session, user_id=user.id)

    @pytest.mark.asyncio
    async def test_check_quota_noop_when_unlimited(self) -> None:
        """With no limit configured (default), check_quota never rejects."""
        user = await UserFactory.create_async(
            session=self.session,
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        )
        usecase = UsageUsecase()
        for _ in range(5):
            await usecase.record_run(
                session=self.session, user_id=user.id, total_tokens=100
            )
        await self.session.commit()

        # Should not raise despite repeated usage.
        await usecase.check_quota(session=self.session, user_id=user.id)
