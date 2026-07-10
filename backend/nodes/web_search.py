"""Web search node handler."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import httpx

from constants.timeout import DEFAULT_TIMEOUT
from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError, WebSearchConnectionError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)

# DuckDuckGo's lite HTML endpoint returns real organic results (title, URL,
# snippet) and needs no API key, unlike the old Instant Answer API this
# replaced — that one only ever populated `AbstractText`/`RelatedTopics` for
# a small set of "definition"-style queries and came back empty for most
# real searches. It blocks requests without a browser-like User-Agent.
_SEARCH_URL = "https://lite.duckduckgo.com/lite/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class _SearchResult:
    """One parsed organic search result."""

    __slots__ = ("href", "snippet", "title")

    def __init__(self, title: str, href: str) -> None:
        """Start a result with its title and target URL; snippet fills in later."""
        self.title = title
        self.href = href
        self.snippet: str | None = None


class _DuckDuckGoLiteParser(HTMLParser):
    """Extracts organic results from a DuckDuckGo lite results page.

    Sponsored results are wrapped in `<tr class="result-sponsored">` and are
    skipped entirely; organic result links carry `class="result-link"` and
    their snippet lives in a sibling `<td class="result-snippet">`.
    """

    def __init__(self) -> None:
        """Initialize parser state."""
        super().__init__(convert_charrefs=True)
        self.results: list[_SearchResult] = []
        self._in_sponsored_row = False
        self._capturing_title = False
        self._capturing_snippet = False
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []
        self._pending_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track sponsored rows and the start of a title/snippet element."""
        attr_map = dict(attrs)
        if tag == "tr":
            classes = (attr_map.get("class") or "").split()
            self._in_sponsored_row = "result-sponsored" in classes
            return
        if self._in_sponsored_row:
            return

        classes = (attr_map.get("class") or "").split()
        if tag == "a" and "result-link" in classes:
            self._capturing_title = True
            self._title_parts = []
            self._pending_href = attr_map.get("href")
        elif tag == "td" and "result-snippet" in classes:
            self._capturing_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag: str) -> None:
        """Finalize a title/snippet element once its closing tag is seen."""
        if tag == "a" and self._capturing_title:
            self._capturing_title = False
            title = "".join(self._title_parts).strip()
            href = self._resolve_href(self._pending_href)
            self._pending_href = None
            if title and href:
                self.results.append(_SearchResult(title=title, href=href))
        elif tag == "td" and self._capturing_snippet:
            self._capturing_snippet = False
            snippet = "".join(self._snippet_parts).strip()
            if snippet:
                for result in reversed(self.results):
                    if result.snippet is None:
                        result.snippet = snippet
                        break

    def handle_data(self, data: str) -> None:
        """Accumulate text for whichever element is currently being captured."""
        if self._capturing_title:
            self._title_parts.append(data)
        elif self._capturing_snippet:
            self._snippet_parts.append(data)

    @staticmethod
    def _resolve_href(href: str | None) -> str | None:
        """Unwrap DuckDuckGo's `/l/?uddg=...` redirect to the real target URL."""
        if not href:
            return None
        if href.startswith("//"):
            href = f"https:{href}"
        parsed = urlparse(href)
        if parsed.path == "/l/":
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            return target or None
        return href


class WebSearchNodeHandler:
    """Handler for web search nodes."""

    _MIN_RESULTS = 1
    _MAX_RESULTS = 10

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Run one web search node and return aggregated text results."""
        query = self._build_query(context)
        max_results = self._read_max_results(context)
        results = await self._search(query)
        lines = self._format_results(results=results, max_results=max_results)

        if lines:
            return NodeExecutionResult(output="\n\n".join(lines))
        return NodeExecutionResult(output=f"No search results found for: {query}")

    def _build_query(self, context: NodeExecutionContext) -> str:
        """Build query text from node inputs."""
        query = "\n".join(context.parent_values).strip() or context.input_value.strip()
        if not query:
            raise ExecutionGraphValidationError(message="Web search query is empty")
        return query

    def _read_max_results(self, context: NodeExecutionContext) -> int:
        """Read and validate max_results from node configuration."""
        max_results = context.node_data.get("max_results")
        if not isinstance(max_results, int) or not (
            self._MIN_RESULTS <= max_results <= self._MAX_RESULTS
        ):
            message = "Web search node requires max_results to be an integer in [1, 10]"
            raise ExecutionGraphValidationError(message=message)

        return max_results

    async def _search(self, query: str) -> list[_SearchResult]:
        """Fetch and parse organic results from DuckDuckGo's lite endpoint."""
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT, headers={"User-Agent": _USER_AGENT}
            ) as client:
                response = await client.get(_SEARCH_URL, params={"q": query})
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException as exc:
            message = "Web search request timed out while running execution"
            raise WebSearchConnectionError(message=message) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            message = f"Web search provider returned {exc.response.status_code}"
            if detail:
                message = f"{message}: {detail[:300]}"
            raise WebSearchConnectionError(message=message) from exc
        except httpx.HTTPError as exc:
            raise WebSearchConnectionError from exc

        parser = _DuckDuckGoLiteParser()
        parser.feed(html)
        return parser.results

    def _format_results(
        self, results: list[_SearchResult], max_results: int
    ) -> list[str]:
        """Build numbered title/snippet/URL blocks from parsed results."""
        lines: list[str] = []
        for index, result in enumerate(results[:max_results], start=1):
            block = [f"{index}. {result.title}"]
            if result.snippet:
                block.append(f"   {result.snippet}")
            block.append(f"   {result.href}")
            lines.append("\n".join(block))

        return lines


def _build_handler(deps: NodeHandlerDeps) -> WebSearchNodeHandler:
    """Build a web search node handler."""
    del deps
    return WebSearchNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.WEB_SEARCH,
    label="Web Search",
    icon_key="web_search",
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
                placeholder="Web search label",
            ),
            default="Web Search node",
        ),
        NodeFieldSpec(
            name="max_results",
            required=True,
            validators={
                ValidatorType.GE.value: 1,
                ValidatorType.LE.value: 10,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.NUMBER,
                label="Max results",
                help="How many search results to include in output.",
                step=1,
            ),
            default=5,
        ),
    ),
    build_handler=_build_handler,
)
