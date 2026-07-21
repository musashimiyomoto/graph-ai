"""HTTP request node handler."""

import json
from typing import cast

import httpx

from constants.timeout import DEFAULT_TIMEOUT
from enums import HttpMethod, NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError, HTTPRequestError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from nodes.rendering import render_input, render_input_url_encoded, upstream_text
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)
from utils.network import blocked_url_reason

_MAX_RESPONSE_CHARS = 10_000
_ALLOWED_SCHEMES = ("http://", "https://")


def _truncate_response(text: str) -> str:
    """Cap a response body's length, with a visible truncation marker.

    Without a marker, a truncated response looks identical to a genuinely
    short one — the caller (or an LLM downstream) has no way to tell the
    data was cut off.
    """
    if len(text) <= _MAX_RESPONSE_CHARS:
        return text
    return f"{text[:_MAX_RESPONSE_CHARS]}\n\n[truncated: {len(text)} chars total]"


class HTTPRequestNodeHandler:
    """Handler for HTTP request nodes."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Perform an HTTP request and return the response body.

        Args:
            context: Node execution context.

        Returns:
            The response body text (truncated).

        Raises:
            ExecutionGraphValidationError: If the node configuration is invalid.
            HTTPRequestError: If the request fails.

        """
        method = self._read_method(context)
        url = self._read_url(context)
        reason = await blocked_url_reason(url)
        if reason is not None:
            raise ExecutionGraphValidationError(message=reason)
        headers = self._read_headers(context)
        body = self._read_body(context, method=method)

        payload = await self._request(
            method=method, url=url, headers=headers, body=body
        )
        return NodeExecutionResult.text(_truncate_response(payload))

    def _read_url(self, context: NodeExecutionContext) -> str:
        """Read, render, and validate the target URL.

        The ``{{input}}`` substitution is percent-encoded (see
        `render_input_url_encoded`) so upstream text containing spaces,
        ``&``, or ``#`` can't corrupt the surrounding URL structure.
        """
        raw_url = context.node_data.get("url")
        if not isinstance(raw_url, str) or not raw_url:
            message = "HTTP request node requires a URL"
            raise ExecutionGraphValidationError(message=message)

        url = render_input_url_encoded(raw_url, context).strip()
        if not url.startswith(_ALLOWED_SCHEMES):
            message = "HTTP request node requires an http(s) URL"
            raise ExecutionGraphValidationError(message=message)
        return url

    def _read_method(self, context: NodeExecutionContext) -> HttpMethod:
        """Read and validate the HTTP method."""
        raw_method = context.node_data.get("method", HttpMethod.GET.value)
        try:
            return HttpMethod(raw_method)
        except ValueError as exc:
            message = "HTTP request node has an unsupported method"
            raise ExecutionGraphValidationError(message=message) from exc

    def _read_headers(self, context: NodeExecutionContext) -> dict[str, str]:
        """Read, template, and validate request headers from a JSON object field."""
        raw_headers = context.node_data.get("headers")
        if raw_headers is None or (
            isinstance(raw_headers, str) and not raw_headers.strip()
        ):
            return {}

        parsed = raw_headers
        if isinstance(raw_headers, str):
            try:
                parsed = json.loads(raw_headers)
            except json.JSONDecodeError as exc:
                message = "HTTP request node headers must be valid JSON"
                raise ExecutionGraphValidationError(message=message) from exc

        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parsed.items()
        ):
            message = "HTTP request node headers must be a JSON object of strings"
            raise ExecutionGraphValidationError(message=message)
        typed_headers = cast("dict[str, str]", parsed)
        return {
            name: render_input(value, context) for name, value in typed_headers.items()
        }

    def _read_body(
        self, context: NodeExecutionContext, method: HttpMethod
    ) -> str | None:
        """Resolve the request body for body-carrying methods."""
        if not method.allows_body:
            return None

        raw_body = context.node_data.get("body")
        if isinstance(raw_body, str) and raw_body:
            return render_input(raw_body, context)
        return upstream_text(context)

    async def _request(
        self,
        method: HttpMethod,
        url: str,
        headers: dict[str, str],
        body: str | None,
    ) -> str:
        """Execute the HTTP request, mapping transport errors to domain errors."""
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.request(
                    method.value.upper(),
                    url,
                    content=body,
                    headers=headers or None,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            message = "HTTP request timed out"
            raise HTTPRequestError(message=message) from exc
        except httpx.HTTPStatusError as exc:
            message = f"HTTP request returned {exc.response.status_code}"
            raise HTTPRequestError(message=message) from exc
        except httpx.HTTPError as exc:
            raise HTTPRequestError from exc

        return response.text


def _build_handler(deps: NodeHandlerDeps) -> HTTPRequestNodeHandler:
    """Build an HTTP request node handler."""
    del deps
    return HTTPRequestNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.HTTP_REQUEST,
    label="HTTP Request",
    icon_key="http_request",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="HTTP request label",
            ),
            default="HTTP Request node",
        ),
        NodeFieldSpec(
            name="method",
            required=True,
            validators={
                ValidatorType.SELECT.value: [member.value for member in HttpMethod]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Method",
                help="POST/PUT/PATCH send a request body.",
            ),
            default=HttpMethod.GET.value,
        ),
        NodeFieldSpec(
            name="url",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="URL",
                placeholder="https://api.example.com/search?q={{input}}",
                help="Supports {{input}} for the upstream text (URL-encoded).",
            ),
            default="",
        ),
        NodeFieldSpec(
            name="headers",
            required=False,
            validators={ValidatorType.JSON.value: True},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Headers (JSON)",
                placeholder='{"Authorization": "Bearer ...", '
                '"Content-Type": "application/json"}',
                help="Optional JSON object of header name/value strings. "
                "Supports {{input}} in values.",
            ),
        ),
        NodeFieldSpec(
            name="body",
            required=False,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Body",
                placeholder='{"query": "{{input}}"}',
                help="Sent for POST/PUT/PATCH. Supports {{input}}. "
                "Leave blank to send the upstream text.",
            ),
        ),
    ),
    build_handler=_build_handler,
)
