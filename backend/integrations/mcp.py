"""Remote Streamable HTTP MCP client helpers."""

import json
from datetime import timedelta
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from constants.timeout import DEFAULT_TIMEOUT
from exceptions import MCPConnectionError
from schemas import MCPToolResponse


async def list_mcp_tools(
    *,
    url: str,
    headers: dict[str, str],
) -> list[MCPToolResponse]:
    """Connect to a server and return its complete tool list."""
    try:
        async with (
            httpx.AsyncClient(
                headers=headers or None,
                timeout=DEFAULT_TIMEOUT,
            ) as client,
            streamable_http_client(url, http_client=client) as streams,
        ):
            read_stream, write_stream, _ = streams
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=DEFAULT_TIMEOUT),
            ) as session:
                await session.initialize()
                tools = []
                cursor: str | None = None
                while True:
                    page = await session.list_tools(cursor=cursor)
                    tools.extend(
                        MCPToolResponse(
                            name=tool.name,
                            description=tool.description,
                            input_schema=tool.inputSchema,
                        )
                        for tool in page.tools
                    )
                    cursor = page.nextCursor
                    if cursor is None:
                        return tools
    except Exception as exc:
        raise MCPConnectionError(message="Could not connect to MCP server") from exc


async def call_mcp_tool(
    *,
    url: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Call one MCP tool and serialize its result as workflow text."""
    try:
        async with (
            httpx.AsyncClient(
                headers=headers or None,
                timeout=DEFAULT_TIMEOUT,
            ) as client,
            streamable_http_client(url, http_client=client) as streams,
        ):
            read_stream, write_stream, _ = streams
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=DEFAULT_TIMEOUT),
            ) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
    except Exception as exc:
        raise MCPConnectionError(message="MCP tool request failed") from exc

    if result.isError:
        message = _result_text(result) or "MCP tool returned an error"
        raise MCPConnectionError(message=message)
    return _result_text(result)


def _result_text(result: CallToolResult) -> str:
    """Convert structured or content-block MCP output to text."""
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent, ensure_ascii=False)
    text_parts = [
        block.text for block in result.content if isinstance(block, TextContent)
    ]
    if text_parts:
        return "\n".join(text_parts)
    return json.dumps(
        [block.model_dump(mode="json", exclude_none=True) for block in result.content],
        ensure_ascii=False,
    )
