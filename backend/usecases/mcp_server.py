"""Saved MCP server business logic."""

import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from credentials import (
    connection_secret,
    create_profile_connection,
    get_profile_connection,
)
from db.models import MCPServer
from db.repositories import ConnectionRepository, MCPServerRepository
from exceptions import (
    BlockedURLError,
    MCPServerAlreadyExistsError,
    MCPServerNotFoundError,
)
from integrations.mcp import list_mcp_tools
from integrations.mcp_registry import search_mcp_registry
from schemas import (
    MCPRegistryServerResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPToolResponse,
)
from usecases.audit import AuditEvent, AuditUsecase
from utils.network import blocked_url_reason


async def mcp_server_response(
    session: AsyncSession, server: MCPServer
) -> MCPServerResponse:
    """Build public metadata without decrypting or exposing headers."""
    connection = await get_profile_connection(
        session=session,
        connection_id=server.connection_id,
        user_id=server.user_id,
    )
    secret = connection_secret(connection) if connection is not None else None
    return MCPServerResponse(
        id=server.id,
        user_id=server.user_id,
        connection_id=server.connection_id,
        name=server.name,
        url=server.url,
        has_headers=bool(secret),
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
            connection = await create_profile_connection(
                session=session,
                user_id=user_id,
                name=data.name,
                provider="mcp",
                secret=json.dumps(data.headers) if data.headers else None,
            )
            created = await self._repository.create(
                session=session,
                data={
                    "user_id": user_id,
                    "name": data.name,
                    "url": data.url,
                    "connection_id": connection.id,
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
        return await mcp_server_response(session, created)

    async def search_catalog(
        self,
        search: str,
        limit: int,
    ) -> list[MCPRegistryServerResponse]:
        """Search usable remote servers in the official registry."""
        return await search_mcp_registry(search=search, limit=limit)

    async def list_servers(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> list[MCPServerResponse]:
        """List saved server metadata."""
        servers = await self._repository.get_all(session=session, user_id=user_id)
        return [await mcp_server_response(session, server) for server in servers]

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
        connection = await get_profile_connection(
            session=session,
            connection_id=server.connection_id,
            user_id=user_id,
        )
        secret = connection_secret(connection) if connection is not None else None
        headers = json.loads(secret) if secret else {}
        return await list_mcp_tools(url=server.url, headers=headers)

    async def delete_server(
        self,
        session: AsyncSession,
        user_id: int,
        server_id: int,
    ) -> None:
        """Delete an owned server."""
        server = await self._get_owned(session, user_id, server_id)
        deleted = await ConnectionRepository().delete_by(
            session=session, id=server.connection_id, user_id=user_id
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
