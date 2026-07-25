"""Plugin node registry and typed-port compatibility tests."""

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, Self, cast

import pytest

from enums import NodeType, PortCoercion, PortType
from exceptions import ExecutionGraphValidationError, VectorCollectionNotFoundError
from nodes import (
    NODE_DEFINITIONS,
    CodeTransformNodeHandler,
    ConditionNodeHandler,
    HTTPRequestNodeHandler,
    NodeValue,
    SwitchNodeHandler,
    TemplateNodeHandler,
    VectorIngestNodeHandler,
    VectorSearchNodeHandler,
    build_node_catalog,
    check_edge_ports,
    coerce_node_value,
    get_node_definition,
    ports_compatible,
    required_port_coercion,
)
from nodes.base import NodeExecutionContext
from rag.ingest import ChunkPayload, ingest_document
from schemas import KnowledgeIngestOptions, VectorUploadResponse
from tests.fakes import FakeQdrantClient

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _context(
    node_data: dict[str, object],
    parent_values: list[str],
    values_by_input: dict[str, list[str]] | None = None,
) -> NodeExecutionContext:
    """Build a minimal node execution context for handler tests."""
    return NodeExecutionContext(
        session=cast("AsyncSession", None),
        workflow_owner_id=1,
        node_data=node_data,
        parent_values=[NodeValue.text(value) for value in parent_values],
        input_value=NodeValue.text(""),
        values_by_input={
            name: tuple(NodeValue.text(value) for value in values)
            for name, values in (values_by_input or {}).items()
        },
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
        if graph.inputs or len(graph.outputs) != 1:
            pytest.fail("Input node port cardinality is wrong")
        if graph.outputs[0].type is not PortType.TEXT:
            pytest.fail("Input node ports are wrong")

    def test_output_node_ports(self) -> None:
        """Output node has a text input and no output port."""
        graph = build_node_catalog()[NodeType.OUTPUT].graph
        if graph.outputs or len(graph.inputs) != 1:
            pytest.fail("Output node port cardinality is wrong")
        if graph.inputs[0].type is not PortType.TEXT:
            pytest.fail("Output node ports are wrong")

    def test_code_node_exposes_configurable_named_ports(self) -> None:
        """Catalog clients can resolve Code port names and allowed types."""
        graph = build_node_catalog()[NodeType.CODE_TRANSFORM].graph
        if [port.name for port in graph.inputs] != ["input"]:
            pytest.fail("Code node did not expose its named input")
        if [port.name for port in graph.outputs] != ["output"]:
            pytest.fail("Code node did not expose its named output")
        expected = {PortType.TEXT, PortType.JSON, PortType.LIST}
        if set(graph.inputs[0].allowed_types) != expected:
            pytest.fail("Code node input options are incomplete")
        if set(graph.outputs[0].allowed_types) != expected:
            pytest.fail("Code node output options are incomplete")

    def test_http_node_exposes_ordinary_multi_ports(self) -> None:
        """HTTP Request publishes independent body, status, and header values."""
        graph = build_node_catalog()[NodeType.HTTP_REQUEST].graph
        if [port.name for port in graph.inputs] != ["input", "body"]:
            pytest.fail("HTTP Request input handles are incomplete")
        if [port.name for port in graph.outputs] != ["body", "status", "headers"]:
            pytest.fail("HTTP Request output handles are incomplete")
        if graph.inputs[1].required:
            pytest.fail("HTTP Request's named body input should remain optional")


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

    def test_mismatched_ports_require_the_declared_coercion(self) -> None:
        """A convertible pair is valid only with its exact edge conversion."""
        required = required_port_coercion(PortType.TEXT, PortType.JSON)
        if required is not PortCoercion.TEXT_TO_JSON:
            pytest.fail("text -> json coercion was not declared")
        if not ports_compatible(
            PortType.TEXT, PortType.JSON, PortCoercion.TEXT_TO_JSON
        ):
            pytest.fail("Declared text -> json coercion should be compatible")
        if ports_compatible(PortType.TEXT, PortType.JSON, PortCoercion.TEXT_TO_LIST):
            pytest.fail("A wrong coercion was accepted")

    def test_coercion_preserves_structured_runtime_value(self) -> None:
        """Edge conversion parses text into JSON rather than hiding it in text."""
        converted = coerce_node_value(
            NodeValue.text('{"answer": 42}'), PortCoercion.TEXT_TO_JSON
        )
        if converted.kind is not PortType.JSON:
            pytest.fail("Text was not converted to a JSON NodeValue")
        if converted.value != {"answer": 42}:
            pytest.fail("JSON coercion changed the structured value")

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
        result = await handler.execute(
            _context(
                {"template": "Summary: {{input}}"},
                parent_values=["hello world"],
            )
        )
        if result.output.require_text() != "Summary: hello world":
            pytest.fail("Template placeholder was not substituted")

    @pytest.mark.asyncio
    async def test_empty_template_rejected(self) -> None:
        """A missing template raises a graph validation error."""
        handler = TemplateNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({}, parent_values=["x"]))

    @pytest.mark.asyncio
    async def test_substitutes_placeholder_with_internal_whitespace(self) -> None:
        """`{{ input }}` substitutes the same as `{{input}}`."""
        handler = TemplateNodeHandler()
        result = await handler.execute(
            _context(
                {"template": "Summary: {{ input }}"},
                parent_values=["hello world"],
            )
        )
        if result.output.require_text() != "Summary: hello world":
            pytest.fail("Whitespace-padded placeholder was not substituted")

    @pytest.mark.asyncio
    async def test_substitutes_uppercase_placeholder(self) -> None:
        """`{{INPUT}}` substitutes the same as `{{input}}`."""
        handler = TemplateNodeHandler()
        result = await handler.execute(
            _context(
                {"template": "Summary: {{INPUT}}"},
                parent_values=["hello world"],
            )
        )
        if result.output.require_text() != "Summary: hello world":
            pytest.fail("Uppercase placeholder was not substituted")

    @pytest.mark.asyncio
    async def test_indexed_placeholder_selects_one_parent(self) -> None:
        """`{{input[N]}}` references a single parent by position."""
        handler = TemplateNodeHandler()
        result = await handler.execute(
            _context(
                {"template": "{{input[1]}} then {{ INPUT[0] }}"},
                parent_values=["first", "second"],
            )
        )
        if result.output.require_text() != "second then first":
            pytest.fail("Indexed placeholder did not select the right parent")

    @pytest.mark.asyncio
    async def test_indexed_placeholder_out_of_range_rejected(self) -> None:
        """An out-of-range index raises a graph validation error."""
        handler = TemplateNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"template": "{{input[2]}}"},
                    parent_values=["only one"],
                )
            )


class _DummyHTTPResponse:
    """Fixed HTTP response for the request-node test."""

    status_code = HTTPStatus.OK
    text = "response body"
    headers: ClassVar[dict[str, str]] = {
        "Content-Type": "text/plain",
        "X-Test": "yes",
    }

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

    async def request(
        self, method: str, url: str, **kwargs: object
    ) -> _DummyHTTPResponse:
        """Record the request and return the fixed response."""
        _DummyHTTPClient.calls = {"method": method, "url": url, **kwargs}
        return _DummyHTTPResponse()


class TestHTTPRequestNode:
    """Tests for the HTTP request node handler."""

    @pytest.mark.asyncio
    async def test_post_falls_back_to_upstream_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST with no body field sends the upstream text."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        result = await handler.execute(
            _context(
                {"url": "https://api.example.com", "method": "post"},
                parent_values=["payload"],
            )
        )
        if result.output.require_text() != "response body":
            pytest.fail("Handler did not return the response body")
        if result.outputs["status"].value != HTTPStatus.OK:
            pytest.fail("Handler did not expose the response status output")
        if result.outputs["headers"].value != _DummyHTTPResponse.headers:
            pytest.fail("Handler did not expose the response headers output")
        if _DummyHTTPClient.calls.get("method") != "POST":
            pytest.fail("Method was not forwarded")
        if _DummyHTTPClient.calls.get("content") != "payload":
            pytest.fail("Upstream text was not sent as the POST body")

    @pytest.mark.asyncio
    async def test_named_body_input_overrides_primary_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The optional body handle supplies content independently of input."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        await handler.execute(
            _context(
                {"url": "https://api.example.com/{{input}}", "method": "post"},
                parent_values=["query", "request-body"],
                values_by_input={
                    "input": ["query"],
                    "body": ["request-body"],
                },
            )
        )
        if _DummyHTTPClient.calls.get("url") != "https://api.example.com/query":
            pytest.fail("Primary input should be used for URL rendering")
        if _DummyHTTPClient.calls.get("content") != "request-body":
            pytest.fail("Named body input should be used as request content")

    @pytest.mark.asyncio
    async def test_renders_url_body_and_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL and body render {{input}}; headers parse from JSON."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        await handler.execute(
            _context(
                {
                    "url": "https://api.example.com/?q={{input}}",
                    "method": "post",
                    "headers": '{"Authorization": "Bearer t"}',
                    "body": '{"query": "{{input}}"}',
                },
                parent_values=["cats"],
            )
        )
        if _DummyHTTPClient.calls.get("url") != "https://api.example.com/?q=cats":
            pytest.fail("URL placeholder was not rendered")
        if _DummyHTTPClient.calls.get("content") != '{"query": "cats"}':
            pytest.fail("Body placeholder was not rendered")
        if _DummyHTTPClient.calls.get("headers") != {"Authorization": "Bearer t"}:
            pytest.fail("Headers were not parsed and forwarded")

    @pytest.mark.asyncio
    async def test_get_sends_no_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET requests carry no body even with upstream text."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        await handler.execute(
            _context(
                {"url": "https://api.example.com", "method": "get"},
                parent_values=["ignored"],
            )
        )
        if _DummyHTTPClient.calls.get("content") is not None:
            pytest.fail("GET requests must not send a body")

    @pytest.mark.asyncio
    async def test_invalid_headers_rejected(self) -> None:
        """Malformed header JSON raises a graph validation error."""
        handler = HTTPRequestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {
                        "url": "https://api.example.com",
                        "method": "get",
                        "headers": "not-json",
                    },
                    parent_values=["x"],
                )
            )

    @pytest.mark.asyncio
    async def test_non_http_url_rejected(self) -> None:
        """A non-http(s) URL raises a graph validation error."""
        handler = HTTPRequestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"url": "ftp://x", "method": "get"}, parent_values=["x"])
            )

    @pytest.mark.asyncio
    async def test_ssrf_loopback_rejected(self) -> None:
        """A loopback URL is blocked by the SSRF guard (strict mode)."""
        handler = HTTPRequestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"url": "http://127.0.0.1/admin", "method": "get"},
                    parent_values=["x"],
                )
            )

    @pytest.mark.asyncio
    async def test_url_input_substitution_is_percent_encoded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Upstream text with spaces/&/# can't corrupt the URL's structure."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        await handler.execute(
            _context(
                {"url": "https://api.example.com/?q={{input}}", "method": "get"},
                parent_values=["cats & dogs #1"],
            )
        )
        expected_url = "https://api.example.com/?q=cats%20%26%20dogs%20%231"
        if _DummyHTTPClient.calls.get("url") != expected_url:
            pytest.fail("Upstream text was not percent-encoded before substitution")

    @pytest.mark.asyncio
    async def test_header_values_render_input_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """{{input}} in a header value is substituted like the URL/body."""
        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _DummyHTTPClient)
        handler = HTTPRequestNodeHandler()
        await handler.execute(
            _context(
                {
                    "url": "https://api.example.com",
                    "method": "get",
                    "headers": '{"X-Query": "{{input}}"}',
                },
                parent_values=["cats"],
            )
        )
        if _DummyHTTPClient.calls.get("headers") != {"X-Query": "cats"}:
            pytest.fail("{{input}} in a header value was not substituted")

    @pytest.mark.asyncio
    async def test_response_truncation_has_visible_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A response over the char cap is truncated with a visible marker."""

        class _LongResponse:
            status_code = 200
            text = "x" * 10_050

            def raise_for_status(self) -> None:
                """Keep the successful status."""

        class _LongResponseClient:
            """Async httpx client returning a fixed over-cap response body."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Accept any httpx kwargs."""

            async def __aenter__(self) -> Self:
                """Enter the context manager."""
                return self

            async def __aexit__(self, *args: object) -> bool:
                """Exit the context manager."""
                return False

            async def request(
                self, method: str, url: str, **kwargs: object
            ) -> _LongResponse:
                """Return the fixed over-cap response."""
                del method, url, kwargs
                return _LongResponse()

        monkeypatch.setattr("nodes.http_request.httpx.AsyncClient", _LongResponseClient)
        handler = HTTPRequestNodeHandler()
        result = await handler.execute(
            _context({"url": "https://api.example.com", "method": "get"}, [])
        )
        output = result.output.require_text()
        if "[truncated: 10050 chars total]" not in output:
            pytest.fail("Truncated response should carry a visible marker")
        if len(output) >= len(_LongResponse.text):
            pytest.fail("Response should actually be truncated, not just marked")


class TestConditionNode:
    """Tests for the condition/router node handler."""

    @pytest.mark.asyncio
    async def test_contains_match_selects_true_branch(self) -> None:
        """A matching contains condition routes to the true handle."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {"condition_type": "contains", "value": "world"},
                parent_values=["hello world"],
            )
        )
        if (
            result.selected_handle != "true"
            or result.output.require_text() != "hello world"
        ):
            pytest.fail("Matching contains condition should select true")

    @pytest.mark.asyncio
    async def test_contains_mismatch_selects_false_branch(self) -> None:
        """A non-matching contains condition routes to the false handle."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {"condition_type": "contains", "value": "bye"},
                parent_values=["hello world"],
            )
        )
        if result.selected_handle != "false":
            pytest.fail("Non-matching contains condition should select false")

    @pytest.mark.asyncio
    async def test_contains_is_case_insensitive_by_default(self) -> None:
        """Case sensitivity defaults to off."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {"condition_type": "contains", "value": "WORLD"},
                parent_values=["hello world"],
            )
        )
        if result.selected_handle != "true":
            pytest.fail("Contains should be case-insensitive by default")

    @pytest.mark.asyncio
    async def test_case_sensitive_contains_respects_case(self) -> None:
        """Setting case_sensitive=true makes contains case-sensitive."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "condition_type": "contains",
                    "value": "WORLD",
                    "case_sensitive": "true",
                },
                parent_values=["hello world"],
            )
        )
        if result.selected_handle != "false":
            pytest.fail("case_sensitive=true should make contains case-sensitive")

    @pytest.mark.asyncio
    async def test_equals_exact_match(self) -> None:
        """Equals condition matches only the exact upstream text."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {"condition_type": "equals", "value": "hello"},
                parent_values=["hello"],
            )
        )
        if result.selected_handle != "true":
            pytest.fail("Exact match should select true")

    @pytest.mark.asyncio
    async def test_regex_match(self) -> None:
        """Regex condition matches against a pattern."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context(
                {"condition_type": "regex", "value": r"^\d+$"},
                parent_values=["12345"],
            )
        )
        if result.selected_handle != "true":
            pytest.fail("Regex match should select true")

    @pytest.mark.asyncio
    async def test_invalid_regex_rejected(self) -> None:
        """An invalid regex pattern raises a graph validation error."""
        handler = ConditionNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"condition_type": "regex", "value": "("},
                    parent_values=["x"],
                )
            )

    @pytest.mark.asyncio
    async def test_not_empty_true_for_non_blank_input(self) -> None:
        """not_empty selects true for non-blank upstream text."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context({"condition_type": "not_empty"}, parent_values=["x"])
        )
        if result.selected_handle != "true":
            pytest.fail("Non-blank input should select true")

    @pytest.mark.asyncio
    async def test_not_empty_false_for_blank_input(self) -> None:
        """not_empty selects false for blank upstream text."""
        handler = ConditionNodeHandler()
        result = await handler.execute(
            _context({"condition_type": "not_empty"}, parent_values=["   "])
        )
        if result.selected_handle != "false":
            pytest.fail("Blank input should select false")

    @pytest.mark.asyncio
    async def test_missing_value_rejected_for_contains(self) -> None:
        """A missing comparison value raises a graph validation error."""
        handler = ConditionNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"condition_type": "contains"}, parent_values=["x"])
            )

    @pytest.mark.asyncio
    async def test_unsupported_condition_type_rejected(self) -> None:
        """An unrecognized condition_type raises a graph validation error."""
        handler = ConditionNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"condition_type": "bogus", "value": "x"}, parent_values=["x"])
            )


class TestSwitchNode:
    """Tests for ordered named Switch routing."""

    @pytest.mark.asyncio
    async def test_first_matching_branch_is_selected(self) -> None:
        """The first exact match wins and leaves upstream text unchanged."""
        handler = SwitchNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "branches": [
                        {"name": "first", "value": "hello"},
                        {"name": "second", "value": "hello"},
                    ],
                    "case_sensitive": "false",
                },
                parent_values=["HELLO"],
            )
        )
        if result.selected_handle != "first" or result.output.require_text() != "HELLO":
            pytest.fail("Switch should select its first case-insensitive match")

    @pytest.mark.asyncio
    async def test_unmatched_value_selects_default(self) -> None:
        """An unmatched value routes through the reserved default handle."""
        handler = SwitchNodeHandler()
        result = await handler.execute(
            _context(
                {"branches": [{"name": "billing", "value": "billing"}]},
                parent_values=["support"],
            )
        )
        if result.selected_handle != "default":
            pytest.fail("Unmatched Switch input should select default")

    @pytest.mark.asyncio
    async def test_case_sensitive_match_respects_case(self) -> None:
        """Case-sensitive mode does not fold the input or comparison value."""
        handler = SwitchNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "branches": [{"name": "billing", "value": "Billing"}],
                    "case_sensitive": "true",
                },
                parent_values=["billing"],
            )
        )
        if result.selected_handle != "default":
            pytest.fail("Case-sensitive Switch match should respect case")

    @pytest.mark.asyncio
    async def test_invalid_configuration_is_rejected(self) -> None:
        """Runtime validation protects executions using old invalid snapshots."""
        handler = SwitchNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"branches": [{"name": "default", "value": "x"}]},
                    parent_values=["x"],
                )
            )


class TestCodeTransformNode:
    """Tests for the code/transform node handler."""

    @pytest.mark.asyncio
    async def test_transforms_input_text(self) -> None:
        """Code runs against the upstream text and returns the output."""
        handler = CodeTransformNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "input_type": "text",
                    "output_type": "text",
                    "code": "output = input.upper()",
                },
                parent_values=["hello world"],
            )
        )
        if result.output.require_text() != "HELLO WORLD":
            pytest.fail("Code node did not transform the input text")

    @pytest.mark.asyncio
    async def test_json_module_is_available(self) -> None:
        """The sandbox exposes the json module for parsing/serializing."""
        handler = CodeTransformNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "input_type": "text",
                    "output_type": "text",
                    "code": (
                        "data = json.loads(input)\noutput = str(data['a'] + data['b'])"
                    ),
                },
                parent_values=['{"a": 1, "b": 2}'],
            )
        )
        if result.output.require_text() != "3":
            pytest.fail("Code node could not use the json module")

    @pytest.mark.asyncio
    async def test_non_string_output_is_json_encoded(self) -> None:
        """A non-string output value is coerced via JSON encoding."""
        handler = CodeTransformNodeHandler()
        result = await handler.execute(
            _context(
                {
                    "input_type": "text",
                    "output_type": "text",
                    "code": "output = [x.strip() for x in input.split(',')]",
                },
                parent_values=["a, b ,c"],
            )
        )
        if result.output.require_text() != '["a", "b", "c"]':
            pytest.fail("Non-string output should be JSON-encoded")

    @pytest.mark.asyncio
    async def test_json_input_can_produce_native_list_output(self) -> None:
        """Configured structured ports expose native values inside the sandbox."""
        handler = CodeTransformNodeHandler()
        context = NodeExecutionContext(
            session=cast("AsyncSession", None),
            workflow_owner_id=1,
            node_data={
                "input_type": "json",
                "output_type": "list",
                "code": "output = input['items']",
            },
            parent_values=[NodeValue.json({"items": [1, 2, 3]})],
            input_value=NodeValue.text(""),
        )

        result = await handler.execute(context)

        if result.output.kind is not PortType.LIST:
            pytest.fail("Code node serialized its list output to text")
        if result.output.value != [1, 2, 3]:
            pytest.fail("Code node changed its structured list output")

    @pytest.mark.asyncio
    async def test_missing_code_rejected(self) -> None:
        """Empty code raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({}, parent_values=["x"]))

    @pytest.mark.asyncio
    async def test_syntax_error_rejected(self) -> None:
        """A syntax error in the code raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({"code": "output = ("}, parent_values=["x"]))

    @pytest.mark.asyncio
    async def test_runtime_error_rejected(self) -> None:
        """A runtime exception in the code raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"code": "output = 1 / 0"}, parent_values=["x"])
            )

    @pytest.mark.asyncio
    async def test_missing_output_assignment_rejected(self) -> None:
        """Code that never assigns 'output' raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"code": "result = input"}, parent_values=["x"])
            )

    @pytest.mark.asyncio
    async def test_import_is_blocked(self) -> None:
        """Attempting to import a module raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"code": "import os\noutput = os.getcwd()"},
                    parent_values=["x"],
                )
            )

    @pytest.mark.asyncio
    async def test_file_access_is_blocked(self) -> None:
        """Attempting to open a file raises a graph validation error."""
        handler = CodeTransformNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context(
                    {"code": "output = open('/etc/passwd').read()"},
                    parent_values=["x"],
                )
            )


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic fake embedding: a single feature, the text length."""
    return [[float(len(text))] for text in texts]


class _NodeVectorUsecase:
    """SQL-free adapter keeping node handler tests focused on node behavior."""

    def __init__(self, client: FakeQdrantClient) -> None:
        """Keep the test's in-memory Qdrant client."""
        self._client = client

    async def ingest_text(  # noqa: PLR0913
        self,
        *,
        session: object,
        user_id: int,
        collection: str,
        text: str,
        source: str,
        options: KnowledgeIngestOptions,
    ) -> VectorUploadResponse:
        """Ingest chunks without exercising the SQL registry in node unit tests."""
        del session
        count = await ingest_document(
            client=cast("AsyncQdrantClient", self._client),
            collection=collection,
            text=text,
            source=source,
            payload=ChunkPayload(
                owner_id=user_id,
                logical_collection=collection,
                source_type=options.source_type,
                external_id=options.external_id,
                revision=options.revision,
                content_hash="0" * 64,
                acl=options.acl.model_dump(),
                metadata=options.metadata,
                expires_at=None,
            ),
        )
        return VectorUploadResponse(source=source, chunks_ingested=count)

    async def resolve_search_collection(
        self, *, session: object, user_id: int, name: str
    ) -> tuple[str, list[str]]:
        """Resolve the literal fake collection and its source payload keys."""
        del session, user_id
        if not await self._client.collection_exists(name):
            raise VectorCollectionNotFoundError
        sources = {
            str(payload.get("source", "doc"))
            for _, payload in self._client.collections[name]
        }
        return name, sorted(sources)


@pytest.fixture
def node_vector_usecase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace SQL-backed vector orchestration in direct node unit tests."""
    monkeypatch.setattr("nodes.vector_ingest.VectorUsecase", _NodeVectorUsecase)
    monkeypatch.setattr("nodes.vector_search.VectorUsecase", _NodeVectorUsecase)


@pytest.mark.usefixtures("node_vector_usecase")
class TestVectorIngestNode:
    """Tests for the vector-ingest node handler."""

    @pytest.mark.asyncio
    async def test_ingest_chunks_and_stores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ingesting text stores one chunk per call and reports the count."""
        client = FakeQdrantClient()
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_ingest.get_qdrant_client", lambda: client)

        handler = VectorIngestNodeHandler()
        result = await handler.execute(
            _context(
                {"collection": "docs", "source": "doc-a"},
                parent_values=["hello world"],
            )
        )

        if result.output.require_text() != "Ingested 1 chunk(s) in 'docs'.":
            pytest.fail("Unexpected confirmation message")
        stored_payload = client.collections["docs"][0][1]
        if (
            stored_payload["text"] != "hello world"
            or stored_payload["source"] != "doc-a"
        ):
            pytest.fail("Chunk text/source was not stored in the collection")

    @pytest.mark.asyncio
    async def test_missing_collection_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty collection name raises a graph validation error."""
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        handler = VectorIngestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({}, parent_values=["hello"]))

    @pytest.mark.asyncio
    async def test_empty_upstream_text_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty upstream text raises a graph validation error."""
        client = FakeQdrantClient()
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_ingest.get_qdrant_client", lambda: client)
        handler = VectorIngestNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"collection": "docs"}, parent_values=["   "])
            )

    @pytest.mark.asyncio
    async def test_reingesting_same_source_replaces_not_appends(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-running the node with the same source replaces its chunks."""
        client = FakeQdrantClient()
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_ingest.get_qdrant_client", lambda: client)
        handler = VectorIngestNodeHandler()
        node_data = {"collection": "docs", "source": "doc-a"}

        await handler.execute(_context(node_data, parent_values=["hello world"]))
        first_count = len(client.collections["docs"])

        await handler.execute(_context(node_data, parent_values=["a different text"]))
        second_count = len(client.collections["docs"])

        if second_count != first_count:
            pytest.fail("Re-ingesting the same source should replace, not append")
        if client.collections["docs"][0][1]["text"] != "a different text":
            pytest.fail("Expected the replaced chunk's text to be the new version")

    @pytest.mark.asyncio
    async def test_different_sources_coexist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two different sources in the same collection don't collide."""
        client = FakeQdrantClient()
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_ingest.get_qdrant_client", lambda: client)
        handler = VectorIngestNodeHandler()

        await handler.execute(
            _context({"collection": "docs", "source": "doc-a"}, parent_values=["hello"])
        )
        await handler.execute(
            _context({"collection": "docs", "source": "doc-b"}, parent_values=["world"])
        )

        sources = {payload["source"] for _, payload in client.collections["docs"]}
        if sources != {"doc-a", "doc-b"}:
            pytest.fail("Expected chunks from both sources to coexist")

    @pytest.mark.asyncio
    async def test_blank_source_falls_back_to_label(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A blank source falls back to the node's label."""
        client = FakeQdrantClient()
        monkeypatch.setattr("rag.ingest.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_ingest.get_qdrant_client", lambda: client)
        handler = VectorIngestNodeHandler()

        await handler.execute(
            _context({"collection": "docs", "label": "My Doc"}, parent_values=["hello"])
        )

        if client.collections["docs"][0][1]["source"] != "My Doc":
            pytest.fail("Expected the node label to be used as the source")


@pytest.mark.usefixtures("node_vector_usecase")
class TestVectorSearchNode:
    """Tests for the vector-search node handler."""

    @pytest.mark.asyncio
    async def test_search_returns_matching_chunks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Search returns up to top_k stored chunks joined by a separator."""
        client = FakeQdrantClient()
        client.collections["docs"] = [
            ([1.0], {"text": "chunk one", "owner_id": 1, "source": "doc"}),
            ([2.0], {"text": "chunk two", "owner_id": 1, "source": "doc"}),
            ([3.0], {"text": "chunk three", "owner_id": 1, "source": "doc"}),
        ]
        monkeypatch.setattr("nodes.vector_search.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_search.get_qdrant_client", lambda: client)

        handler = VectorSearchNodeHandler()
        result = await handler.execute(
            _context({"collection": "docs", "top_k": 2}, parent_values=["a query"])
        )

        if result.output.require_text() != "chunk one\n\n---\n\nchunk two":
            pytest.fail("Search did not return the expected chunks in order")

    @pytest.mark.asyncio
    async def test_nonexistent_collection_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Searching a collection that was never ingested into raises an error."""
        client = FakeQdrantClient()
        monkeypatch.setattr("nodes.vector_search.embed_texts", _fake_embed_texts)
        monkeypatch.setattr("nodes.vector_search.get_qdrant_client", lambda: client)

        handler = VectorSearchNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"collection": "missing", "top_k": 4}, parent_values=["query"])
            )

    @pytest.mark.asyncio
    async def test_missing_collection_rejected(self) -> None:
        """An empty collection name raises a graph validation error."""
        handler = VectorSearchNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(_context({"top_k": 4}, parent_values=["query"]))

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty upstream query raises a graph validation error."""
        client = FakeQdrantClient()
        client.collections["docs"] = []
        monkeypatch.setattr("nodes.vector_search.get_qdrant_client", lambda: client)

        handler = VectorSearchNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"collection": "docs", "top_k": 4}, parent_values=["  "])
            )

    @pytest.mark.asyncio
    async def test_invalid_top_k_rejected(self) -> None:
        """A top_k outside [1, 20] raises a graph validation error."""
        handler = VectorSearchNodeHandler()
        with pytest.raises(ExecutionGraphValidationError):
            await handler.execute(
                _context({"collection": "docs", "top_k": 0}, parent_values=["query"])
            )
