"""Plugin node registry and typed-port compatibility tests."""

from typing import TYPE_CHECKING, ClassVar, Self, cast

import pytest

from enums import NodeType, PortType
from exceptions import ExecutionGraphValidationError
from nodes import (
    NODE_DEFINITIONS,
    HTTPRequestNodeHandler,
    TemplateNodeHandler,
    build_node_catalog,
    check_edge_ports,
    get_node_definition,
    ports_compatible,
)
from nodes.base import NodeExecutionContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _context(
    node_data: dict[str, object], parent_values: list[str]
) -> NodeExecutionContext:
    """Build a minimal node execution context for handler tests."""
    return NodeExecutionContext(
        session=cast("AsyncSession", None),
        workflow_owner_id=1,
        node_data=node_data,
        parent_values=parent_values,
        input_value="",
    )


class TestRegistryCompleteness:
    """Tests that every node type is registered exactly once."""

    def test_every_type_has_one_definition(self) -> None:
        """Each NodeType maps to exactly one definition."""
        types = [definition.type for definition in NODE_DEFINITIONS]
        if sorted(types) != sorted(NodeType):
            pytest.fail("NODE_DEFINITIONS does not cover every NodeType exactly once")

    def test_catalog_covers_all_types(self) -> None:
        """The derived catalog contains an entry per node type."""
        catalog = build_node_catalog()
        if set(catalog) != set(NodeType):
            pytest.fail("Catalog does not cover every node type")

    def test_get_definition_returns_requested_type(self) -> None:
        """Lookup returns the definition for the requested type."""
        if get_node_definition(NodeType.LLM).type is not NodeType.LLM:
            pytest.fail("Lookup returned the wrong definition")


class TestCatalogPorts:
    """Tests that catalog entries expose port metadata."""

    def test_input_node_ports(self) -> None:
        """Input node has a text output and no input port."""
        graph = build_node_catalog()[NodeType.INPUT].graph
        if graph.input_port is not None or graph.output_port is not PortType.TEXT:
            pytest.fail("Input node ports are wrong")

    def test_output_node_ports(self) -> None:
        """Output node has a text input and no output port."""
        graph = build_node_catalog()[NodeType.OUTPUT].graph
        if graph.output_port is not None or graph.input_port is not PortType.TEXT:
            pytest.fail("Output node ports are wrong")


class TestPortCompatibility:
    """Tests for port compatibility checks."""

    def test_same_type_is_compatible(self) -> None:
        """Identical port types are compatible."""
        if not ports_compatible(PortType.TEXT, PortType.TEXT):
            pytest.fail("Matching ports should be compatible")

    def test_different_type_is_incompatible(self) -> None:
        """Different port types are not compatible."""
        if ports_compatible(PortType.TEXT, PortType.JSON):
            pytest.fail("Mismatched ports must be incompatible")

    def test_text_to_text_edge_ok(self) -> None:
        """A text output feeding a text input is valid."""
        if check_edge_ports(NodeType.INPUT, NodeType.OUTPUT) is not None:
            pytest.fail("input -> output should be a valid connection")

    def test_source_without_output_port_rejected(self) -> None:
        """A node without an output port cannot be a source."""
        if check_edge_ports(NodeType.OUTPUT, NodeType.INPUT) is None:
            pytest.fail("Output node has no output port and cannot be a source")

    def test_target_without_input_port_rejected(self) -> None:
        """A node without an input port cannot be a target."""
        if check_edge_ports(NodeType.INPUT, NodeType.INPUT) is None:
            pytest.fail("Input node has no input port and cannot be a target")


class TestTemplateNode:
    """Tests for the prompt/template node handler."""

    @pytest.mark.asyncio
    async def test_substitutes_placeholder(self) -> None:
        """The upstream text replaces the {{input}} placeholder."""
        handler = TemplateNodeHandler()
        output = await handler.execute(
            _context(
                {"template": "Summary: {{input}}"},
                parent_values=["hello world"],
            )
        )
        if output != "Summary: hello world":
            pytest.fail("Template placeholder was not substituted")

    @pytest.mark.asyncio
    async def test_empty_template_rejected(self) -> None:
        """A missing template raises a graph validation error."""
        handler = TemplateNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({}, parent_values=["x"]))


class _DummyHTTPResponse:
    """Fixed HTTP response for the request-node test."""

    status_code = 200
    text = "response body"

    def raise_for_status(self) -> None:
        """Keep the successful status."""


class _DummyHTTPClient:
    """Async httpx client capturing the request and returning a fixed body."""

    calls: ClassVar[dict[str, object]] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept any httpx kwargs."""

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit the context manager."""
        return False

    async def post(self, url: str, **kwargs: object) -> _DummyHTTPResponse:
        """Record a POST call and return the fixed response."""
        _DummyHTTPClient.calls = {"method": "post", "url": url, **kwargs}
        return _DummyHTTPResponse()

    async def get(self, url: str, **kwargs: object) -> _DummyHTTPResponse:
        """Record a GET call and return the fixed response."""
        _DummyHTTPClient.calls = {"method": "get", "url": url, **kwargs}
        return _DummyHTTPResponse()


class TestHTTPRequestNode:
    """Tests for the HTTP request node handler."""

    @pytest.mark.asyncio
    async def test_post_sends_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A POST request forwards the upstream text as the body."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        output = await handler.execute(
            _context(
                {"url": "https://api.example.com", "method": "post"},
                parent_values=["payload"],
            )
        )
        if output != "response body":
            pytest.fail("Handler did not return the response body")
        if _DummyHTTPClient.calls.get("content") != "payload":
            pytest.fail("Upstream text was not sent as the POST body")

    @pytest.mark.asyncio
    async def test_non_http_url_rejected(self) -> None:
        """A non-http(s) URL raises a graph validation error."""
        handler = HTTPRequestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"url": "ftp://x", "method": "get"}, parent_values=["x"])
            )
