"""MCP server dependency providers."""

from usecases import MCPServerUsecase


def get_mcp_server_usecase() -> MCPServerUsecase:
    """Build an MCP server usecase."""
    return MCPServerUsecase()
