"""Official MCP Registry discovery client with a short in-process cache."""

import asyncio
import re
import time
from typing import Any, cast

import httpx

from constants.timeout import DEFAULT_TIMEOUT
from exceptions import MCPConnectionError
from schemas import MCPRegistryInputResponse, MCPRegistryServerResponse

_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
_CACHE_TTL_SECONDS = 3600
_VARIABLE_PATTERN = re.compile(r"\{(?P<key>[A-Za-z][A-Za-z0-9_]*)\}")
_cache: dict[tuple[str, int], tuple[float, list[MCPRegistryServerResponse]]] = {}
_cache_lock = asyncio.Lock()


async def search_mcp_registry(
    *,
    search: str,
    limit: int,
) -> list[MCPRegistryServerResponse]:
    """Search active remote servers in the official MCP Registry."""
    key = (search.casefold(), limit)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    async with _cache_lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    _REGISTRY_URL,
                    params={"search": search, "limit": limit},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MCPConnectionError(
                message="Official MCP Registry request failed"
            ) from exc

        results = _normalize_registry_payload(payload)
        _cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, results)
        return results


def _normalize_registry_payload(payload: object) -> list[MCPRegistryServerResponse]:
    """Keep latest active Streamable HTTP remotes and normalize their inputs."""
    if not isinstance(payload, dict):
        raise MCPConnectionError(message="Official MCP Registry returned invalid data")
    payload_data = cast("dict[str, Any]", payload)
    servers = payload_data.get("servers")
    if not isinstance(servers, list):
        raise MCPConnectionError(message="Official MCP Registry returned invalid data")

    results: list[MCPRegistryServerResponse] = []
    for entry in servers:
        normalized = _normalize_registry_entry(entry)
        if normalized is not None:
            results.append(normalized)
    return results


def _normalize_registry_entry(entry: object) -> MCPRegistryServerResponse | None:
    """Normalize one registry response entry, if it is usable remotely."""
    server = _active_latest_server(entry)
    if server is None:
        return None
    remote = _streamable_remote(server)
    if remote is None:
        return None

    registry_name = server.get("name")
    version = server.get("version")
    if not isinstance(registry_name, str) or not isinstance(version, str):
        return None
    url_template = str(remote["url"])
    header_templates = _header_templates(remote.get("headers"))
    input_specs = _collect_inputs(remote, url_template, header_templates)
    repository = server.get("repository")
    repository_url = (
        repository.get("url")
        if isinstance(repository, dict) and isinstance(repository.get("url"), str)
        else None
    )
    return MCPRegistryServerResponse(
        registry_name=registry_name,
        name=registry_name.rsplit("/", maxsplit=1)[-1],
        description=(
            server.get("description")
            if isinstance(server.get("description"), str)
            else None
        ),
        version=version,
        url_template=url_template,
        header_templates=header_templates,
        inputs=input_specs,
        repository_url=repository_url,
    )


def _active_latest_server(entry: object) -> dict[str, Any] | None:
    """Return server data only for the latest active registry entry."""
    if not isinstance(entry, dict):
        return None
    entry_data = cast("dict[str, Any]", entry)
    server = entry_data.get("server")
    metadata = entry_data.get("_meta")
    if not isinstance(server, dict) or not isinstance(metadata, dict):
        return None
    official = metadata.get("io.modelcontextprotocol.registry/official")
    if (
        not isinstance(official, dict)
        or official.get("status") != "active"
        or official.get("isLatest") is not True
    ):
        return None
    return server


def _streamable_remote(server: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first usable Streamable HTTP remote transport."""
    remotes = server.get("remotes")
    if not isinstance(remotes, list):
        return None
    return next(
        (
            item
            for item in remotes
            if isinstance(item, dict)
            and item.get("type") == "streamable-http"
            and isinstance(item.get("url"), str)
        ),
        None,
    )


def _header_templates(raw_headers: object) -> dict[str, str]:
    """Extract header name/value templates from a remote transport."""
    if not isinstance(raw_headers, list):
        return {}
    result: dict[str, str] = {}
    for header in raw_headers:
        if not isinstance(header, dict):
            continue
        header_data = cast("dict[str, Any]", header)
        name = header_data.get("name")
        if isinstance(name, str):
            result[name] = str(header_data.get("value", ""))
    return result


def _collect_inputs(
    remote: dict[str, Any],
    url_template: str,
    header_templates: dict[str, str],
) -> list[MCPRegistryInputResponse]:
    """Merge declared and template-inferred URL/header inputs."""
    declared: dict[str, dict[str, Any]] = {}
    raw_variables = remote.get("variables")
    if isinstance(raw_variables, dict):
        declared.update(
            (str(key), value)
            for key, value in raw_variables.items()
            if isinstance(value, dict)
        )
    raw_headers = remote.get("headers")
    if isinstance(raw_headers, list):
        for header in raw_headers:
            if not isinstance(header, dict):
                continue
            variables = header.get("variables")
            if isinstance(variables, dict):
                declared.update(
                    (str(key), value)
                    for key, value in variables.items()
                    if isinstance(value, dict)
                )
            for match in _VARIABLE_PATTERN.finditer(str(header.get("value", ""))):
                spec = declared.setdefault(match.group("key"), {})
                if header.get("isSecret") is True:
                    spec["isSecret"] = True
                if header.get("description") and "description" not in spec:
                    spec["description"] = header["description"]

    referenced = {
        match.group("key")
        for template in (url_template, *header_templates.values())
        for match in _VARIABLE_PATTERN.finditer(template)
    }
    return [
        MCPRegistryInputResponse(
            key=key,
            description=(
                spec.get("description")
                if isinstance(spec.get("description"), str)
                else None
            ),
            placeholder=(
                spec.get("placeholder")
                if isinstance(spec.get("placeholder"), str)
                else None
            ),
            default=(
                spec.get("default") if isinstance(spec.get("default"), str) else None
            ),
            required=spec.get("isRequired", True) is not False,
            secret=spec.get("isSecret") is True,
        )
        for key in sorted(referenced)
        for spec in [declared.get(key, {})]
    ]
