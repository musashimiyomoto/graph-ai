"""HTTP request node handler."""

import httpx

from constants.timeout import DEFAULT_TIMEOUT
from enums import HttpMethod, NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError, HTTPRequestError
from nodes.base import NodeExecutionContext
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)

_MAX_RESPONSE_CHARS = 10_000
_ALLOWED_SCHEMES = ("http://", "https://")


class HTTPRequestNodeHandler:
    """Handler for HTTP request nodes."""

    async def execute(self, context: NodeExecutionContext) -> str:
        """Perform an HTTP request and return the response body.

        Args:
            context: Node execution context.

        Returns:
            The response body text (truncated).

        Raises:
            ExecutionGraphValidationError: If the node configuration is invalid.
            HTTPRequestError: If the request fails.

        """
        url = self._read_url(context)
        method = self._read_method(context)
        body = (
            "\n".join(context.parent_values)
            if context.parent_values
            else context.input_value
        )

        payload = await self._request(method=method, url=url, body=body)
        return payload[:_MAX_RESPONSE_CHARS]

    def _read_url(self, context: NodeExecutionContext) -> str:
        """Read and validate the target URL."""
        url = context.node_data.get("url")
        if not isinstance(url, str) or not url.startswith(_ALLOWED_SCHEMES):
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

    async def _request(self, method: HttpMethod, url: str, body: str) -> str:
        """Execute the HTTP request, mapping transport errors to domain errors."""
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                if method is HttpMethod.POST:
                    response = await client.post(url, content=body)
                else:
                    response = await client.get(url)
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
            name="url",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="URL",
                placeholder="https://api.example.com/endpoint",
            ),
            default="",
        ),
        NodeFieldSpec(
            name="method",
            required=True,
            validators={
                ValidatorType.SELECT.value: [
                    HttpMethod.GET.value,
                    HttpMethod.POST.value,
                ]
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Method",
                help="POST sends the upstream text as the request body.",
            ),
            default=HttpMethod.GET.value,
        ),
    ),
    build_handler=_build_handler,
)
