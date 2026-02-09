"""Node API tests."""

import uuid

import pytest

from enums import NodeType
from enums.node import InputNodeFormat, OutputNodeFormat
from tests.factories import NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase

NODE_DATA_BY_TYPE: dict[NodeType, dict] = {
    NodeType.INPUT: {
        "label": f"node-{uuid.uuid4().hex[:8]}",
        "format": InputNodeFormat.TXT,
    },
    NodeType.LLM: {
        "label": f"node-{uuid.uuid4().hex[:8]}",
        "llm_provider": "openai",
        "model": "gpt-4",
        "system_prompt": "You are a helpful assistant.",
        "temperature": 0.7,
    },
    NodeType.OUTPUT: {
        "label": f"node-{uuid.uuid4().hex[:8]}",
        "format": OutputNodeFormat.TXT,
    },
}

EXPECTED_FIELDS_BY_TYPE: dict[NodeType, set[str]] = {
    NodeType.INPUT: {"label", "format"},
    NodeType.LLM: {"label", "llm_provider", "model", "system_prompt", "temperature"},
    NodeType.OUTPUT: {"label", "format"},
}


class TestNodeCreate(BaseTestCase):
    """Tests for POST /nodes."""

    url = "/nodes"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful creation returns node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        payload = {
            "workflow_id": workflow.id,
            "type": node_type,
            "data": NODE_DATA_BY_TYPE[node_type],
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
        if data["type"] != node_type:
            pytest.fail(f"Node type did not match: {data['type']} != {node_type}")


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
            data=NODE_DATA_BY_TYPE[NodeType.OUTPUT],
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


class TestNodeFields(BaseTestCase):
    """Tests for GET /nodes/fields."""

    url = "/nodes/fields"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Returns fields only for the requested node type."""
        response = await self.client.get(url=self.url, params={"node_type": node_type})

        data = await self.assert_response_list(response=response)
        field_names = {field["name"] for field in data}
        expected = EXPECTED_FIELDS_BY_TYPE[node_type]
        if not expected.issubset(field_names):
            missing = expected - field_names
            pytest.fail(f"Missing expected fields for {node_type}: {missing}")


class TestNodeUpdate(BaseTestCase):
    """Tests for PATCH /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful update returns updated node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=node_type,
            data=NODE_DATA_BY_TYPE[node_type],
        )
        new_x = 42.0
        new_y = 24.0

        response = await self.client.patch(
            url=f"{self.url}/{node.id}",
            json={
                "data": NODE_DATA_BY_TYPE[node_type],
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
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful delete removes the node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=node_type,
            data=NODE_DATA_BY_TYPE[node_type],
        )

        response = await self.client.delete(
            url=f"{self.url}/{node.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if node.id in ids:
            pytest.fail("Expected deleted node to not appear in list")
