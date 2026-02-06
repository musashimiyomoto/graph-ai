"""Execution API tests."""

from http import HTTPStatus

import pytest

from enums import ExecutionStatus
from tests.factories import ExecutionFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestExecutionCreate(BaseTestCase):
    """Tests for POST /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns execution data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"seed": 1}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"id", "workflow_id", "status", "started_at"})
        if data["workflow_id"] != workflow.id:
            pytest.fail("Execution workflow_id did not match request")
        if data["status"] != ExecutionStatus.CREATED:
            pytest.fail("Execution status did not match default")


class TestExecutionList(BaseTestCase):
    """Tests for GET /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns executions for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        first = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )
        second = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected executions to appear in list")


class TestExecutionGet(BaseTestCase):
    """Tests for GET /executions/{execution_id}."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful request returns execution data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        execution = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.get(
            url=f"{self.url}/{execution.id}",
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["id"] != execution.id:
            pytest.fail("Execution id did not match")


class TestExecutionUpdate(BaseTestCase):
    """Tests for PATCH /executions/{execution_id}."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated execution data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        execution = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.patch(
            url=f"{self.url}/{execution.id}",
            json={
                "status": ExecutionStatus.SUCCESS,
                "output_data": {"result": "ok"},
            },
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution status was not updated")
        if data.get("finished_at") is None:
            pytest.fail("Expected finished_at to be set on success")


class TestExecutionDelete(BaseTestCase):
    """Tests for DELETE /executions/{execution_id}."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the execution."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        execution = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.delete(
            url=f"{self.url}/{execution.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=f"{self.url}/{execution.id}",
            headers=headers,
        )
        if fetch.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected deleted execution to return 404")
