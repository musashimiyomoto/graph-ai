"""Saved MCP server API tests."""

import json
from typing import TYPE_CHECKING, cast

import pytest

from db.repositories import MCPServerRepository
from tests.test_api.base import BaseTestCase
from utils.encryption import decrypt

if TYPE_CHECKING:
    from db.models import MCPServer


class TestMCPServerApi(BaseTestCase):
    """MCP server creation, secrecy, discovery, and deletion."""

    url = "/mcp-servers"

    async def test_create_encrypts_headers_and_never_returns_them(self) -> None:
        """Authentication headers are encrypted and write-only."""
        _, headers = await self.create_user_and_get_token()
        secret_headers = {"Authorization": "Bearer secret"}
        response = await self.client.post(
            self.url,
            json={
                "name": "Company tools",
                "url": "https://mcp.example.com/mcp",
                "headers": secret_headers,
            },
            headers=headers,
        )
        data = await self.assert_response_dict(response=response)
        if "headers" in data or data["has_headers"] is not True:
            pytest.fail("MCP headers must be write-only")
        stored = await MCPServerRepository().get_by(
            session=self.session,
            id=data["id"],
        )
        if stored is None:
            pytest.fail("MCP server was not persisted")
        encrypted_headers = cast("MCPServer", stored).headers
        if encrypted_headers == json.dumps(secret_headers):
            pytest.fail("MCP headers were not encrypted")
        if json.loads(decrypt(encrypted_headers)) != secret_headers:
            pytest.fail("Encrypted MCP headers did not round-trip")

    async def test_tool_discovery_uses_owned_server(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tool discovery returns the integration result."""
        _, headers = await self.create_user_and_get_token()
        created_response = await self.client.post(
            self.url,
            json={
                "name": "Tools",
                "url": "https://mcp.example.com/mcp",
                "headers": {},
            },
            headers=headers,
        )
        created = await self.assert_response_dict(response=created_response)

        async def fake_list_tools(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "name": "search",
                    "description": "Search docs",
                    "input_schema": {"type": "object"},
                }
            ]

        monkeypatch.setattr("usecases.mcp_server.list_mcp_tools", fake_list_tools)
        response = await self.client.get(
            f"{self.url}/{created['id']}/tools",
            headers=headers,
        )
        data = await self.assert_response_list(response=response)
        if data[0]["name"] != "search":
            pytest.fail("MCP tool discovery returned the wrong tool")

    async def test_catalog_returns_normalized_registry_results(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The catalog endpoint proxies normalized official registry entries."""

        async def fake_search(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "registry_name": "example/search",
                    "name": "search",
                    "description": "Search docs",
                    "version": "1.0.0",
                    "url_template": "https://mcp.example.com/mcp",
                    "header_templates": {},
                    "inputs": [],
                    "repository_url": None,
                }
            ]

        monkeypatch.setattr("usecases.mcp_server.search_mcp_registry", fake_search)
        response = await self.client.get(f"{self.url}/catalog?search=search")
        data = await self.assert_response_list(response=response)
        if data[0]["registry_name"] != "example/search":
            pytest.fail("MCP catalog returned the wrong normalized server")
