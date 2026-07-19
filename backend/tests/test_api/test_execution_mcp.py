"""MCP Tool workflow execution tests."""

import pytest

from db.repositories import MCPServerRepository
from enums import ExecutionStatus, NodeType
from tests.factories import EdgeFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase
from tests.test_api.test_execution import run_execution
from utils.encryption import encrypt


class TestExecutionMCPTool(BaseTestCase):
    """MCP tools execute as visible workflow graph nodes."""

    @pytest.mark.asyncio
    async def test_mcp_tool_output_reaches_workflow_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rendered upstream arguments are passed to the configured tool."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )
        server = await MCPServerRepository().create(
            session=self.session,
            data={
                "user_id": user["id"],
                "name": "Tools",
                "url": "https://mcp.example.com/mcp",
                "headers": encrypt("{}"),
            },
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        tool_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.MCP_TOOL,
            data={
                "label": "Search",
                "mcp_server_id": server.id,
                "tool_name": "search",
                "arguments": '{"query":"{{input}}"}',
            },
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        for source_id, target_id in (
            (input_node.id, tool_node.id),
            (tool_node.id, output_node.id),
        ):
            await EdgeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                source_node_id=source_id,
                target_node_id=target_id,
            )
        await self.session.commit()
        captured: dict[str, object] = {}

        async def fake_call(**kwargs: object) -> str:
            captured.update(kwargs)
            return "found result"

        async def allow_url(_url: str) -> None:
            return None

        monkeypatch.setattr("nodes.mcp_tool.call_mcp_tool", fake_call)
        monkeypatch.setattr("nodes.mcp_tool.blocked_url_reason", allow_url)

        response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow.id, "input_data": {"value": "docs"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)
        execution = await run_execution(self.session, created["id"])

        if execution.status is not ExecutionStatus.SUCCESS:
            pytest.fail("MCP Tool workflow should succeed")
        if execution.output_data != {"value": "found result"}:
            pytest.fail("MCP Tool output did not reach the Output node")
        if captured["arguments"] != {"query": "docs"}:
            pytest.fail("MCP Tool did not receive rendered upstream arguments")
