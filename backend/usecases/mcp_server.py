"""Saved MCP server business logic."""

import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MCPServer
from db.repositories import MCPServerRepository
from exceptions import (
    BlockedURLError,
    MCPServerAlreadyExistsError,
    MCPServerNotFoundError,
)
from integrations.mcp import list_mcp_tools
from schemas import MCPServerCreate, MCPServerResponse, MCPToolResponse
from usecases.audit import AuditEvent, AuditUsecase
from utils.encryption import decrypt, encrypt
from utils.network import blocked_url_reason


def mcp_server_response(server: MCPServer) -> MCPServerResponse:
    """Build public metadata without decrypting or exposing headers."""
    headers = json.loads(decrypt(server.headers))
    return MCPServerResponse(
        id=server.id,
        user_id=server.user_id,
        name=server.name,
        url=server.url,
        has_headers=bool(headers),
    )


class MCPServerUsecase:
    """CRUD and tool discovery for remote MCP servers."""

    def __init__(self) -> None:
        """Initialize dependencies."""
        self._repository = MCPServerRepository()
        self._audit_usecase = AuditUsecase()

    async def create_server(
        self,
        session: AsyncSession,
        user_id: int,
        data: MCPServerCreate,
    ) -> MCPServerResponse:
        """Validate, encrypt, and save an MCP server."""
        reason = await blocked_url_reason(data.url)
        if reason is not None:
            raise BlockedURLError(message=reason)
        try:
            created = await self._repository.create(
                session=session,
                data={
                    "user_id": user_id,
                    "name": data.name,
                    "url": data.url,
                    "headers": encrypt(json.dumps(data.headers)),
                },
            )
        except IntegrityError as exc:
            await session.rollback()
            raise MCPServerAlreadyExistsError from exc
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="mcp_server.create",
                entity_type="mcp_server",
                entity_id=created.id,
                metadata={"name": created.name, "url": created.url},
            ),
        )
        await session.commit()
        return mcp_server_response(created)

    async def list_servers(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> list[MCPServerResponse]:
        """List saved server metadata."""
        servers = await self._repository.get_all(session=session, user_id=user_id)
        return [mcp_server_response(server) for server in servers]

    async def list_tools(
        self,
        session: AsyncSession,
        user_id: int,
        server_id: int,
    ) -> list[MCPToolResponse]:
        """Discover tools on one owned server."""
        server = await self._get_owned(session, user_id, server_id)
        reason = await blocked_url_reason(server.url)
        if reason is not None:
            raise BlockedURLError(message=reason)
        headers = json.loads(decrypt(server.headers))
        return await list_mcp_tools(url=server.url, headers=headers)

    async def delete_server(
        self,
        session: AsyncSession,
        user_id: int,
        server_id: int,
    ) -> None:
        """Delete an owned server."""
        deleted = await self._repository.delete_by(
            session=session,
            id=server_id,
            user_id=user_id,
        )
        if not deleted:
            raise MCPServerNotFoundError
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="mcp_server.delete",
                entity_type="mcp_server",
                entity_id=server_id,
            ),
        )
        await session.commit()

    async def _get_owned(
        self,
        session: AsyncSession,
        user_id: int,
        server_id: int,
    ) -> MCPServer:
        """Return an owned server or raise not-found."""
        server = await self._repository.get_by(
            session=session,
            id=server_id,
            user_id=user_id,
        )
        if server is None:
            raise MCPServerNotFoundError
        return server
