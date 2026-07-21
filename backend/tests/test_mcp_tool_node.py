"""MCP Tool node handler tests."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from nodes import NodeValue
from nodes.base import NodeExecutionContext
from nodes.mcp_tool import MCPToolNodeHandler

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.repositories import MCPServerRepository


class _Repository:
    """Return one owned MCP server."""

    async def get_by(self, **_kwargs: object) -> SimpleNamespace:
        """Return encrypted server metadata."""
        return SimpleNamespace(
            url="https://mcp.example.com/mcp",
            headers="encrypted",
        )


@pytest.mark.asyncio
async def test_mcp_tool_renders_arguments_and_returns_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler templates upstream input into JSON tool arguments."""
    captured: dict[str, object] = {}

    async def fake_call(**kwargs: object) -> str:
        captured.update(kwargs)
        return "tool result"

    monkeypatch.setattr("nodes.mcp_tool.decrypt", lambda _value: "{}")
    monkeypatch.setattr("nodes.mcp_tool.blocked_url_reason", lambda _url: _none())
    monkeypatch.setattr("nodes.mcp_tool.call_mcp_tool", fake_call)
    handler = MCPToolNodeHandler(cast("MCPServerRepository", _Repository()))
    result = await handler.execute(
        NodeExecutionContext(
            session=cast("AsyncSession", None),
            workflow_owner_id=1,
            node_data={
                "mcp_server_id": 1,
                "tool_name": "search",
                "arguments": '{"query":"{{input}}"}',
            },
            parent_values=[NodeValue.text("hello")],
            input_value=NodeValue.text(""),
        )
    )
    if result.output.require_text() != "tool result":
        pytest.fail("MCP tool output was not returned")
    if captured["arguments"] != {"query": "hello"}:
        pytest.fail("MCP tool arguments were not rendered")


async def _none() -> None:
    """Return None from an awaitable network check stub."""
