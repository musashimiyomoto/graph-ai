"""Workflow export/import/duplicate API tests."""

from http import HTTPStatus

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import NodeType
from enums.node import InputNodeFormat, OutputNodeFormat
from tests.factories import (
    EdgeFactory,
    LLMProviderFactory,
    NodeFactory,
    TelegramBotFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase

_EXPECTED_NODE_COUNT = 3
_EXPECTED_EDGE_COUNT = 2


async def _build_input_llm_output_graph(
    session: AsyncSession,
    workflow_id: int,
    *,
    llm_provider_id: int,
    telegram_bot_id: int | None = None,
) -> tuple[list, list]:
    """Create a simple Input -> LLM -> Output graph for a workflow.

    Returns:
        A tuple of (nodes, edges) in creation order.

    """
    input_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.INPUT,
        data={"label": "in", "format": InputNodeFormat.TXT},
    )
    llm_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.LLM,
        data={
            "label": "llm",
            "llm_provider_id": llm_provider_id,
            "model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
        },
    )
    output_data: dict = {"label": "out", "format": OutputNodeFormat.TXT}
    if telegram_bot_id is not None:
        output_data = {
            "label": "out",
            "format": OutputNodeFormat.TELEGRAM,
            "telegram_bot_id": telegram_bot_id,
        }
    output_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.OUTPUT,
        data=output_data,
    )

    first_edge = await EdgeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        source_node_id=input_node.id,
        target_node_id=llm_node.id,
    )
    second_edge = await EdgeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        source_node_id=llm_node.id,
        target_node_id=output_node.id,
    )

    return [input_node, llm_node, output_node], [first_edge, second_edge]


async def _build_graph_with_loop(
    session: AsyncSession, workflow_id: int
) -> dict[str, object]:
    """Create an Input -> Loop(list) -> Output graph with a one-node body.

    Returns:
        A dict of node ids/positions useful for asserting the rebuilt graph.

    """
    input_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.INPUT,
        data={"label": "in", "format": InputNodeFormat.TXT},
    )
    loop_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.LOOP,
        data={"label": "loop", "mode": "list"},
    )
    output_node = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.OUTPUT,
        data={"label": "out", "format": OutputNodeFormat.TXT},
    )
    loop_input = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.LOOP_INPUT,
        data={"label": "loop in"},
        parent_node_id=loop_node.id,
    )
    loop_output = await NodeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        type=NodeType.LOOP_OUTPUT,
        data={"label": "loop out"},
        parent_node_id=loop_node.id,
    )
    await EdgeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        source_node_id=input_node.id,
        target_node_id=loop_node.id,
    )
    await EdgeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        source_node_id=loop_node.id,
        target_node_id=output_node.id,
    )
    await EdgeFactory.create_async(
        session=session,
        workflow_id=workflow_id,
        source_node_id=loop_input.id,
        target_node_id=loop_output.id,
    )
    return {
        "loop_node_id": loop_node.id,
        "loop_input_id": loop_input.id,
        "loop_output_id": loop_output.id,
    }


class TestWorkflowTransferPreservesLoopStructure(BaseTestCase):
    """Tests that export/import/duplicate preserve a Loop node's body scope."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_export_carries_parent_index_for_body_nodes(self) -> None:
        """Body nodes export with parent_index pointing at the Loop node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_graph_with_loop(self.session, workflow.id)

        response = await self.client.get(
            url=f"{self.url}/{workflow.id}/export", headers=headers
        )

        data = await self.assert_response_dict(response=response)
        nodes = data["graph"]["nodes"]
        by_type: dict[str, list[dict]] = {}
        for index, node in enumerate(nodes):
            by_type.setdefault(node["type"], []).append({**node, "_index": index})

        loop_index = by_type[NodeType.LOOP.value][0]["_index"]
        for body_type in (NodeType.LOOP_INPUT.value, NodeType.LOOP_OUTPUT.value):
            if by_type[body_type][0]["parent_index"] != loop_index:
                pytest.fail(f"{body_type} should export with parent_index=loop index")
        for top_level_type in (NodeType.INPUT.value, NodeType.OUTPUT.value):
            if by_type[top_level_type][0]["parent_index"] is not None:
                pytest.fail(f"{top_level_type} should export with parent_index=None")

    @pytest.mark.asyncio
    async def test_import_rebuilds_loop_body_scope(self) -> None:
        """Importing an exported Loop graph re-parents body nodes to the new Loop id."""
        user, headers = await self.create_user_and_get_token()
        source_workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_graph_with_loop(self.session, source_workflow.id)
        export_response = await self.client.get(
            url=f"{self.url}/{source_workflow.id}/export", headers=headers
        )
        export_data = await self.assert_response_dict(response=export_response)

        import_response = await self.client.post(
            url="/workflows/import",
            json={"name": "imported loop", "graph": export_data["graph"]},
            headers=headers,
        )
        imported = await self.assert_response_dict(response=import_response)

        nodes_response = await self.client.get(
            url=f"/nodes?workflow_id={imported['id']}", headers=headers
        )
        nodes = await self.assert_response_list(response=nodes_response)
        by_type = {node["type"]: node for node in nodes}
        new_loop_id = by_type[NodeType.LOOP.value]["id"]

        for body_type in (NodeType.LOOP_INPUT.value, NodeType.LOOP_OUTPUT.value):
            if by_type[body_type]["parent_node_id"] != new_loop_id:
                pytest.fail(
                    f"Imported {body_type} should be re-parented to the new Loop id"
                )
        for top_level_type in (NodeType.INPUT.value, NodeType.OUTPUT.value):
            if by_type[top_level_type]["parent_node_id"] is not None:
                pytest.fail(f"Imported {top_level_type} should stay top-level")

    @pytest.mark.asyncio
    async def test_duplicate_rebuilds_loop_body_scope(self) -> None:
        """Duplicating a workflow with a Loop node re-parents body nodes too."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_graph_with_loop(self.session, workflow.id)

        response = await self.client.post(
            url=f"{self.url}/{workflow.id}/duplicate", headers=headers
        )
        duplicated = await self.assert_response_dict(response=response)

        nodes_response = await self.client.get(
            url=f"/nodes?workflow_id={duplicated['id']}", headers=headers
        )
        nodes = await self.assert_response_list(response=nodes_response)
        by_type = {node["type"]: node for node in nodes}
        new_loop_id = by_type[NodeType.LOOP.value]["id"]

        for body_type in (NodeType.LOOP_INPUT.value, NodeType.LOOP_OUTPUT.value):
            if by_type[body_type]["parent_node_id"] != new_loop_id:
                pytest.fail(
                    f"Duplicated {body_type} should be re-parented to the new Loop id"
                )


class TestWorkflowExport(BaseTestCase):
    """Tests for GET /workflows/{workflow_id}/export."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_scrubs_account_private_references(self) -> None:
        """Export nulls the private refs but keeps the model/collection strings."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_input_llm_output_graph(
            self.session,
            workflow.id,
            llm_provider_id=provider.id,
            telegram_bot_id=bot.id,
        )

        response = await self.client.get(
            url=f"{self.url}/{workflow.id}/export", headers=headers
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != workflow.name:
            pytest.fail("Exported name did not match workflow name")

        nodes_by_type = {node["type"]: node for node in data["graph"]["nodes"]}
        llm_data = nodes_by_type[NodeType.LLM.value]["data"]
        if llm_data["llm_provider_id"] is not None:
            pytest.fail("Expected llm_provider_id to be scrubbed to null")
        if llm_data["model"] != "gpt-4":
            pytest.fail("Expected model string to survive export unscrubbed")

        output_data = nodes_by_type[NodeType.OUTPUT.value]["data"]
        if output_data["telegram_bot_id"] is not None:
            pytest.fail("Expected telegram_bot_id to be scrubbed to null")

    @pytest.mark.asyncio
    async def test_edges_reference_nodes_by_index(self) -> None:
        """Exported edges use list position, not database node IDs."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_input_llm_output_graph(
            self.session, workflow.id, llm_provider_id=provider.id
        )

        response = await self.client.get(
            url=f"{self.url}/{workflow.id}/export", headers=headers
        )

        data = await self.assert_response_dict(response=response)
        edges = data["graph"]["edges"]
        if len(edges) != _EXPECTED_EDGE_COUNT:
            pytest.fail(f"Expected {_EXPECTED_EDGE_COUNT} edges, got {len(edges)}")
        if edges[0]["source_index"] != 0 or edges[0]["target_index"] != 1:
            pytest.fail("First edge should link node index 0 -> 1")
        if edges[1]["source_index"] != 1 or edges[1]["target_index"] != 2:  # noqa: PLR2004
            pytest.fail("Second edge should link node index 1 -> 2")

    @pytest.mark.asyncio
    async def test_not_found_for_another_users_workflow(self) -> None:
        """Exporting another user's workflow returns 404."""
        _, headers = await self.create_user_and_get_token()
        other_user, _ = await self.create_user_and_get_token()
        other_workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=other_user["id"]
        )

        response = await self.client.get(
            url=f"{self.url}/{other_workflow.id}/export", headers=headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected {HTTPStatus.NOT_FOUND}, got {response.status_code}")


class TestWorkflowImport(BaseTestCase):
    """Tests for POST /workflows/import."""

    url = "/workflows/import"

    @pytest.mark.asyncio
    async def test_rebuilds_graph_with_unset_references(self) -> None:
        """Importing an export with scrubbed refs succeeds and rebuilds the graph."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        source_workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_input_llm_output_graph(
            self.session, source_workflow.id, llm_provider_id=provider.id
        )
        export_response = await self.client.get(
            url=f"/workflows/{source_workflow.id}/export", headers=headers
        )
        export_data = await self.assert_response_dict(response=export_response)

        response = await self.client.post(
            url=self.url,
            json={"name": "imported workflow", "graph": export_data["graph"]},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != "imported workflow":
            pytest.fail("Imported workflow name did not match request")

        nodes_response = await self.client.get(
            url=f"/nodes?workflow_id={data['id']}", headers=headers
        )
        nodes_data = await self.assert_response_list(response=nodes_response)
        if len(nodes_data) != _EXPECTED_NODE_COUNT:
            pytest.fail(f"Expected {_EXPECTED_NODE_COUNT} nodes, got {len(nodes_data)}")

        llm_node = next(
            node for node in nodes_data if node["type"] == NodeType.LLM.value
        )
        if llm_node["data"]["llm_provider_id"] is not None:
            pytest.fail("Expected imported llm_provider_id to stay unset")

        edges_response = await self.client.get(
            url=f"/edges?workflow_id={data['id']}", headers=headers
        )
        edges_data = await self.assert_response_list(response=edges_response)
        if len(edges_data) != _EXPECTED_EDGE_COUNT:
            pytest.fail(f"Expected {_EXPECTED_EDGE_COUNT} edges, got {len(edges_data)}")

    @pytest.mark.asyncio
    async def test_out_of_range_edge_index_rejected(self) -> None:
        """An edge referencing a node index outside the payload is rejected."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url=self.url,
            json={
                "name": "broken",
                "graph": {
                    "nodes": [
                        {
                            "type": NodeType.INPUT.value,
                            "data": {
                                "label": "in",
                                "format": InputNodeFormat.TXT.value,
                            },
                            "position_x": 0.0,
                            "position_y": 0.0,
                        }
                    ],
                    "edges": [
                        {"source_index": 0, "target_index": 5, "source_handle": None}
                    ],
                },
            },
            headers=headers,
        )

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            message = (
                f"Expected {HTTPStatus.UNPROCESSABLE_ENTITY}, got "
                f"{response.status_code}"
            )
            pytest.fail(message)

    @pytest.mark.asyncio
    async def test_does_not_leave_orphaned_workflow_on_bad_edge(self) -> None:
        """An out-of-range edge index fails before any workflow row is created."""
        _, headers = await self.create_user_and_get_token()

        await self.client.post(
            url=self.url,
            json={
                "name": "broken",
                "graph": {
                    "nodes": [
                        {
                            "type": NodeType.INPUT.value,
                            "data": {
                                "label": "in",
                                "format": InputNodeFormat.TXT.value,
                            },
                            "position_x": 0.0,
                            "position_y": 0.0,
                        }
                    ],
                    "edges": [
                        {"source_index": 0, "target_index": 9, "source_handle": None}
                    ],
                },
            },
            headers=headers,
        )

        list_response = await self.client.get(url="/workflows", headers=headers)
        data = await self.assert_response_list(response=list_response)
        names = {item["name"] for item in data}
        if "broken" in names:
            pytest.fail("Expected no orphaned workflow to be created")


class TestWorkflowDuplicate(BaseTestCase):
    """Tests for POST /workflows/{workflow_id}/duplicate."""

    url = "/workflows"

    @pytest.mark.asyncio
    async def test_preserves_account_private_references(self) -> None:
        """Duplicate keeps llm_provider_id/telegram_bot_id (same account)."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await _build_input_llm_output_graph(
            self.session,
            workflow.id,
            llm_provider_id=provider.id,
            telegram_bot_id=bot.id,
        )

        response = await self.client.post(
            url=f"{self.url}/{workflow.id}/duplicate", headers=headers
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != f"{workflow.name} (copy)":
            pytest.fail("Duplicate name did not follow the '(copy)' convention")

        nodes_response = await self.client.get(
            url=f"/nodes?workflow_id={data['id']}", headers=headers
        )
        nodes_data = await self.assert_response_list(response=nodes_response)
        llm_node = next(
            node for node in nodes_data if node["type"] == NodeType.LLM.value
        )
        if llm_node["data"]["llm_provider_id"] != provider.id:
            pytest.fail("Expected llm_provider_id to be preserved on duplicate")

        output_node = next(
            node for node in nodes_data if node["type"] == NodeType.OUTPUT.value
        )
        if output_node["data"]["telegram_bot_id"] != bot.id:
            pytest.fail("Expected telegram_bot_id to be preserved on duplicate")

    @pytest.mark.asyncio
    async def test_not_found_for_another_users_workflow(self) -> None:
        """Duplicating another user's workflow returns 404."""
        _, headers = await self.create_user_and_get_token()
        other_user, _ = await self.create_user_and_get_token()
        other_workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=other_user["id"]
        )

        response = await self.client.post(
            url=f"{self.url}/{other_workflow.id}/duplicate", headers=headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected {HTTPStatus.NOT_FOUND}, got {response.status_code}")
