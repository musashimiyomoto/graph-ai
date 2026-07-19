"""Official MCP Registry response normalization tests."""

import pytest

from integrations.mcp_registry import _normalize_registry_payload


def test_registry_keeps_active_streamable_http_and_infers_inputs() -> None:
    """Remote templates become a safe configuration form contract."""
    payload = {
        "servers": [
            {
                "server": {
                    "name": "example/search",
                    "description": "Search company documents",
                    "version": "1.2.0",
                    "repository": {
                        "url": "https://github.com/example/search",
                    },
                    "remotes": [
                        {
                            "type": "streamable-http",
                            "url": "https://mcp.example.com/{workspace}/mcp",
                            "variables": {
                                "workspace": {
                                    "description": "Workspace slug",
                                    "isRequired": True,
                                }
                            },
                            "headers": [
                                {
                                    "name": "Authorization",
                                    "value": "Bearer {api_key}",
                                    "description": "API token",
                                    "isSecret": True,
                                    "isRequired": True,
                                }
                            ],
                        }
                    ],
                },
                "_meta": {
                    "io.modelcontextprotocol.registry/official": {
                        "status": "active",
                        "isLatest": True,
                    }
                },
            }
        ]
    }

    results = _normalize_registry_payload(payload)

    if len(results) != 1:
        pytest.fail("Expected one usable registry server")
    server = results[0]
    if server.url_template != "https://mcp.example.com/{workspace}/mcp":
        pytest.fail("Registry URL template was not preserved")
    inputs = {item.key: item for item in server.inputs}
    if not inputs["api_key"].secret or not inputs["api_key"].required:
        pytest.fail("Secret header input metadata was not inferred")
    if inputs["workspace"].description != "Workspace slug":
        pytest.fail("Declared URL variable metadata was not preserved")


def test_registry_filters_deprecated_and_stdio_only_entries() -> None:
    """Only latest active Streamable HTTP entries are exposed."""
    entries = []
    for status, remote_type in (
        ("deprecated", "streamable-http"),
        ("active", "stdio"),
    ):
        entries.append(
            {
                "server": {
                    "name": f"example/{remote_type}",
                    "version": "1.0.0",
                    "remotes": [{"type": remote_type, "url": "https://example.com"}],
                },
                "_meta": {
                    "io.modelcontextprotocol.registry/official": {
                        "status": status,
                        "isLatest": True,
                    }
                },
            }
        )

    if _normalize_registry_payload({"servers": entries}):
        pytest.fail("Unusable registry entries should be filtered")
