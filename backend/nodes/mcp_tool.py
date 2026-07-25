"""MCP tool node handler."""

import json
from typing import Any, cast

from credentials import connection_secret
from db.repositories import ConnectionRepository, MCPServerRepository
from enums import NodeType, PortType, ValidatorType
from exceptions import (
    ExecutionGraphValidationError,
    MCPServerNotFoundError,
)
from integrations.mcp import call_mcp_tool
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps, graph_spec
from nodes.rendering import render_input
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
)
from utils.network import blocked_url_reason


class MCPToolNodeHandler:
    """Call a configured tool on an owned remote MCP server."""

    def __init__(
        self,
        repository: MCPServerRepository,
        connection_repository: ConnectionRepository,
    ) -> None:
        """Store the MCP server repository."""
        self._repository = repository
        self._connection_repository = connection_repository

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Render arguments, invoke the tool, and return its text result."""
        server_id = context.node_data.get("mcp_server_id")
        tool_name = context.node_data.get("tool_name")
        if not isinstance(server_id, int) or server_id <= 0:
            raise ExecutionGraphValidationError(
                message="MCP Tool node requires an MCP server"
            )
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ExecutionGraphValidationError(
                message="MCP Tool node requires a tool name"
            )

        server = await self._repository.get_by(
            session=context.session,
            id=server_id,
            user_id=context.workflow_owner_id,
        )
        if server is None:
            raise MCPServerNotFoundError
        reason = await blocked_url_reason(server.url)
        if reason is not None:
            raise ExecutionGraphValidationError(message=reason)

        arguments = self._read_arguments(context)
        connection = await self._connection_repository.get_by(
            session=context.session,
            id=server.connection_id,
            user_id=context.workflow_owner_id,
        )
        secret = connection_secret(connection) if connection is not None else None
        headers = cast("dict[str, str]", json.loads(secret)) if secret else {}
        output = await call_mcp_tool(
            url=server.url,
            headers=headers,
            tool_name=tool_name,
            arguments=arguments,
        )
        return NodeExecutionResult.text(output)

    def _read_arguments(self, context: NodeExecutionContext) -> dict[str, Any]:
        """Render and parse the JSON object passed as tool arguments."""
        raw = context.node_data.get("arguments")
        if not isinstance(raw, str) or not raw.strip():
            return {}
        try:
            parsed = json.loads(render_input(raw, context))
        except json.JSONDecodeError as exc:
            raise ExecutionGraphValidationError(
                message="MCP Tool arguments must render to valid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise ExecutionGraphValidationError(
                message="MCP Tool arguments must be a JSON object"
            )
        return cast("dict[str, Any]", parsed)


def _build_handler(deps: NodeHandlerDeps) -> MCPToolNodeHandler:
    """Build an MCP Tool node handler."""
    return MCPToolNodeHandler(
        deps.mcp_server_repository,
        deps.connection_repository,
    )


DEFINITION = NodeDefinition(
    type=NodeType.MCP_TOOL,
    label="MCP Tool",
    icon_key="mcp_tool",
    graph=graph_spec(
        input_type=PortType.TEXT,
        output_type=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="MCP tool label",
            ),
            default="MCP Tool",
        ),
        NodeFieldSpec(
            name="mcp_server_id",
            required=True,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.MCP_SERVER,
                label="MCP server",
            ),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.MCP_SERVER),
        ),
        NodeFieldSpec(
            name="tool_name",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.MCP_TOOL,
                label="Tool",
                help="Tools are discovered live from the selected server.",
            ),
            datasource=NodeFieldDataSource(
                kind=NodeFieldDataSourceKind.MCP_TOOL,
                depends_on="mcp_server_id",
            ),
        ),
        NodeFieldSpec(
            name="arguments",
            required=True,
            validators={ValidatorType.JSON.value: True},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Arguments (JSON)",
                placeholder='{"query": "{{input}}"}',
                help="Use {{input}} or {{input[N]}} in JSON string values.",
            ),
            default='{"input": "{{input}}"}',
        ),
    ),
    build_handler=_build_handler,
)
