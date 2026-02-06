"""Node API tests."""

import uuid
from http import HTTPStatus

import pytest

from enums import NodeType
from tests.factories import NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestNodeCreate(BaseTestCase):
    """Tests for POST /nodes."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.INPUT,
            "data": {"label": f"node-{uuid.uuid4().hex[:8]}"},
            "position_x": 10.0,
            "position_y": 20.0,
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "workflow_id", "type", "data", "position_x", "position_y"},
        )
        if data["workflow_id"] != workflow.id:
            pytest.fail("Node workflow_id did not match request")
        if data["type"] != NodeType.INPUT:
            pytest.fail("Node type did not match request")


class TestNodeList(BaseTestCase):
    """Tests for GET /nodes."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns nodes for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        first = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        second = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected nodes to appear in list")


class TestNodeGet(BaseTestCase):
    """Tests for GET /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful request returns node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.get(
            url=f"{self.url}/{node.id}",
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["id"] != node.id:
            pytest.fail("Node id did not match")


class TestNodeUpdate(BaseTestCase):
    """Tests for PATCH /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )
        new_x = 42.0
        new_y = 24.0

        response = await self.client.patch(
            url=f"{self.url}/{node.id}",
            json={
                "data": {"label": f"node-{uuid.uuid4().hex[:8]}"},
                "position_x": new_x,
                "position_y": new_y,
            },
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["position_x"] != new_x or data["position_y"] != new_y:
            pytest.fail("Node positions were not updated")


class TestNodeDelete(BaseTestCase):
    """Tests for DELETE /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.delete(
            url=f"{self.url}/{node.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=f"{self.url}/{node.id}",
            headers=headers,
        )
        if fetch.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected deleted node to return 404")
