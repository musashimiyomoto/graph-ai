"""Edge API tests."""

from http import HTTPStatus

import pytest

from enums import NodeType, PortCoercion
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

    @pytest.mark.asyncio
    async def test_incompatible_ports_rejected(self) -> None:
        """Connecting into an input node (no input port) returns 400."""
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
            type=NodeType.INPUT,
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

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail(
                f"Expected 400 for incompatible ports, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_convertible_ports_require_explicit_coercion(self) -> None:
        """A typed mismatch is rejected until the edge declares its conversion."""
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
            type=NodeType.CODE_TRANSFORM,
            data={
                "label": "Parse",
                "input_type": "json",
                "output_type": "json",
                "code": "output = input",
            },
        )
        payload = {
            "workflow_id": workflow.id,
            "source_node_id": source.id,
            "target_node_id": target.id,
        }

        missing = await self.client.post(url=self.url, json=payload, headers=headers)
        if missing.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Convertible ports connected without an explicit coercion")

        created = await self.client.post(
            url=self.url,
            json={**payload, "coercion": PortCoercion.TEXT_TO_JSON},
            headers=headers,
        )
        data = await self.assert_response_dict(response=created)
        if data["coercion"] != PortCoercion.TEXT_TO_JSON:
            pytest.fail("Created edge did not persist its explicit coercion")

    @pytest.mark.asyncio
    async def test_duplicate_edge_rejected(self) -> None:
        """Creating an identical edge twice returns 409."""
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
        payload = {
            "workflow_id": workflow.id,
            "source_node_id": source.id,
            "target_node_id": target.id,
        }

        first_response = await self.client.post(
            url=self.url, json=payload, headers=headers
        )
        await self.assert_response_dict(response=first_response)

        second_response = await self.client.post(
            url=self.url, json=payload, headers=headers
        )

        if second_response.status_code != HTTPStatus.CONFLICT:
            pytest.fail(
                f"Expected 409 for a duplicate edge, got {second_response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_multiple_handles_between_same_nodes_are_distinct(self) -> None:
        """Default and named target handles persist as separate edges."""
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
            type=NodeType.HTTP_REQUEST,
        )

        created = []
        for target_handle in (None, "body"):
            response = await self.client.post(
                url=self.url,
                json={
                    "workflow_id": workflow.id,
                    "source_node_id": source.id,
                    "target_node_id": target.id,
                    "target_handle": target_handle,
                },
                headers=headers,
            )
            created.append(await self.assert_response_dict(response=response))

        if {edge["target_handle"] for edge in created} != {None, "body"}:
            pytest.fail("Edges did not preserve their distinct target handles")

    @pytest.mark.asyncio
    async def test_unknown_target_handle_rejected(self) -> None:
        """An edge cannot target an input absent from the node definition."""
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
            type=NodeType.HTTP_REQUEST,
        )
        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "source_node_id": source.id,
                "target_node_id": target.id,
                "target_handle": "missing",
            },
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail(
                f"Expected 400 for unknown target handle, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_switch_accepts_configured_and_default_handles(self) -> None:
        """Switch edges may use configured branch names or the default fallback."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.SWITCH,
            data={
                "label": "Switch",
                "branches": [{"name": "billing", "value": "billing"}],
                "case_sensitive": "false",
            },
        )
        targets = [
            await NodeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                type=NodeType.OUTPUT,
            )
            for _ in range(2)
        ]

        for target, source_handle in zip(
            targets,
            ("billing", "default"),
            strict=True,
        ):
            response = await self.client.post(
                url=self.url,
                json={
                    "workflow_id": workflow.id,
                    "source_node_id": source.id,
                    "target_node_id": target.id,
                    "source_handle": source_handle,
                },
                headers=headers,
            )
            await self.assert_response_dict(response=response)

    @pytest.mark.asyncio
    async def test_switch_rejects_unknown_handle(self) -> None:
        """Switch edges cannot reference a branch absent from node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        source = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.SWITCH,
            data={
                "label": "Switch",
                "branches": [{"name": "billing", "value": "billing"}],
                "case_sensitive": "false",
            },
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
                "source_handle": "support",
            },
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail(
                f"Expected 400 for unknown Switch handle, got {response.status_code}"
            )


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
