"""Workflow API tests."""

import uuid

import pytest

from tests.factories import UserFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestWorkflowCreate(BaseTestCase):
    """Tests for POST /workflows."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns workflow data."""
        user, headers = await self.create_user_and_get_token()
        payload = {"name": f"workflow-{uuid.uuid4().hex[:8]}"}

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "owner_id", "name", "created_at", "updated_at"},
        )
        if data["name"] != payload["name"]:
            pytest.fail("Workflow name did not match request")
        if data["owner_id"] != user["id"]:
            pytest.fail("Workflow owner did not match current user")


class TestWorkflowList(BaseTestCase):
    """Tests for GET /workflows."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns workflows for the current user only."""
        user, headers = await self.create_user_and_get_token()
        other = await UserFactory.create_async(session=self.session)

        first = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        second = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        other_workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=other.id
        )

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected workflows to appear in list")
        if other_workflow.id in ids:
            pytest.fail("Unexpected workflow from another user in list")


class TestWorkflowUpdate(BaseTestCase):
    """Tests for PATCH /workflows/{workflow_id}."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated workflow data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        new_name = f"workflow-{uuid.uuid4().hex[:8]}"

        response = await self.client.patch(
            url=f"{self.url}/{workflow.id}",
            json={"name": new_name},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != new_name:
            pytest.fail("Workflow name was not updated")


class TestWorkflowDelete(BaseTestCase):
    """Tests for DELETE /workflows/{workflow_id}."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        response = await self.client.delete(
            url=f"{self.url}/{workflow.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=self.url,
            headers=headers,
        )
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if workflow.id in ids:
            pytest.fail("Expected deleted workflow to not appear in list")
