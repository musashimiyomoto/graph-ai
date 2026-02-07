"""Edge API tests."""

import pytest

from enums import NodeType
from tests.factories import EdgeFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestEdgeCreate(BaseTestCase):
    """Tests for POST /edges."""

    url = "/edges"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns edge data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "source_node_id": source.id,
                "target_node_id": target.id,
            },
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "workflow_id", "source_node_id", "target_node_id"},
        )
        if data["workflow_id"] != workflow.id:
            pytest.fail("Edge workflow_id did not match request")


class TestEdgeList(BaseTestCase):
    """Tests for GET /edges."""

    url = "/edges"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns edges for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )
        second_target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )

        first = await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=source.id,
            target_node_id=target.id,
        )
        second = await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=source.id,
            target_node_id=second_target.id,
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected edges to appear in list")


class TestEdgeUpdate(BaseTestCase):
    """Tests for PATCH /edges/{edge_id}."""

    url = "/edges"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated edge data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )
        edge = await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=source.id,
            target_node_id=target.id,
        )
        new_target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )

        response = await self.client.patch(
            url=f"{self.url}/{edge.id}",
            json={"target_node_id": new_target.id},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["target_node_id"] != new_target.id:
            pytest.fail("Edge target node was not updated")


class TestEdgeDelete(BaseTestCase):
    """Tests for DELETE /edges/{edge_id}."""

    url = "/edges"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the edge."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        target = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
        )
        edge = await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=source.id,
            target_node_id=target.id,
        )

        response = await self.client.delete(
            url=f"{self.url}/{edge.id}",
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
        if edge.id in ids:
            pytest.fail("Expected deleted edge to not appear in list")
