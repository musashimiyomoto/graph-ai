"""Saved MCP server API routes."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, mcp_server
from schemas import (
    MCPRegistryServerResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPToolResponse,
    UserResponse,
)

router = APIRouter(prefix="/mcp-servers", tags=["MCP Servers"])


@router.get(path="/catalog")
async def search_catalog(
    usecase: Annotated[
        mcp_server.MCPServerUsecase,
        Depends(dependency=mcp_server.get_mcp_server_usecase),
    ],
    search: Annotated[str, Query(max_length=128)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[MCPRegistryServerResponse]:
    """Search remote Streamable HTTP servers in the official registry."""
    return await usecase.search_catalog(search=search.strip(), limit=limit)


@router.post(path="")
async def create_server(
    data: Annotated[MCPServerCreate, Body()],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        mcp_server.MCPServerUsecase,
        Depends(dependency=mcp_server.get_mcp_server_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> MCPServerResponse:
    """Register a remote MCP server."""
    return await usecase.create_server(
        session=session,
        user_id=current_user.id,
        data=data,
    )


@router.get(path="")
async def list_servers(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        mcp_server.MCPServerUsecase,
        Depends(dependency=mcp_server.get_mcp_server_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[MCPServerResponse]:
    """List owned MCP servers."""
    return await usecase.list_servers(session=session, user_id=current_user.id)


@router.get(path="/{server_id}/tools")
async def list_tools(
    server_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        mcp_server.MCPServerUsecase,
        Depends(dependency=mcp_server.get_mcp_server_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[MCPToolResponse]:
    """Discover tools exposed by an owned MCP server."""
    return await usecase.list_tools(
        session=session,
        user_id=current_user.id,
        server_id=server_id,
    )


@router.delete(path="/{server_id}")
async def delete_server(
    server_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        mcp_server.MCPServerUsecase,
        Depends(dependency=mcp_server.get_mcp_server_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete an owned MCP server."""
    await usecase.delete_server(
        session=session,
        user_id=current_user.id,
        server_id=server_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "MCP server deleted"},
    )
