"""Repository for saved MCP servers."""

from db.models import MCPServer
from db.repositories.base import BaseRepository


class MCPServerRepository(BaseRepository[MCPServer]):
    """Repository for MCP server configurations."""

    def __init__(self) -> None:
        """Initialize the repository."""
        super().__init__(model=MCPServer)
