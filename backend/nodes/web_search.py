"""Web search node handler."""

from typing import Any

import httpx

from constants.timeout import DEFAULT_TIMEOUT
from exceptions import ExecutionGraphValidationError, WebSearchConnectionError
from nodes.base import NodeExecutionContext


class WebSearchNodeHandler:
    """Handler for web search nodes."""

    _SEARCH_URL = "https://api.duckduckgo.com/"
    _MIN_RESULTS = 1
    _MAX_RESULTS = 10

    async def execute(self, context: NodeExecutionContext) -> str:
        """Run one web search node and return aggregated text results."""
        query = self._build_query(context)
        max_results = self._read_max_results(context)
        payload = await self._search(query)
        lines = self._format_results(payload=payload, max_results=max_results)

        if lines:
            return "\n".join(lines)
        return f"No search results found for: {query}"

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

    async def _search(self, query: str) -> dict[str, Any]:
        """Execute DuckDuckGo search request."""
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    self._SEARCH_URL,
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                    },
                )
                response.raise_for_status()
                payload = response.json()
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
        except ValueError as exc:
            message = "Web search provider returned malformed JSON"
            raise WebSearchConnectionError(message=message) from exc

        if not isinstance(payload, dict):
            message = "Web search provider returned invalid payload format"
            raise WebSearchConnectionError(message=message)

        return payload

    def _format_results(self, payload: dict[str, Any], max_results: int) -> list[str]:
        """Build numbered lines from DuckDuckGo payload."""
        items: list[tuple[str, str | None]] = []
        abstract = payload.get("AbstractText")
        if isinstance(abstract, str) and abstract.strip():
            abstract_url = payload.get("AbstractURL")
            items.append(
                (
                    abstract.strip(),
                    abstract_url.strip()
                    if isinstance(abstract_url, str) and abstract_url.strip()
                    else None,
                )
            )

        items.extend(self._extract_related_topics(payload.get("RelatedTopics")))

        lines: list[str] = []
        for index, (text, url) in enumerate(items[:max_results], start=1):
            suffix = f" ({url})" if url else ""
            lines.append(f"{index}. {text}{suffix}")

        return lines

    def _extract_related_topics(self, value: object) -> list[tuple[str, str | None]]:
        """Extract textual items from RelatedTopics, including nested groups."""
        if not isinstance(value, list):
            return []

        entries: list[dict[str, Any]] = []
        for entry in value:
            entry_dict = self._to_str_key_dict(entry)
            if entry_dict is not None:
                entries.append(entry_dict)

        items: list[tuple[str, str | None]] = []
        stack = entries.copy()

        while stack:
            entry = stack.pop()
            topics = entry.get("Topics")
            if isinstance(topics, list):
                for item in topics:
                    topic_dict = self._to_str_key_dict(item)
                    if topic_dict is not None:
                        stack.append(topic_dict)
                continue

            text = entry.get("Text")
            if not isinstance(text, str) or not text.strip():
                continue

            first_url = entry.get("FirstURL")
            url = (
                first_url.strip()
                if isinstance(first_url, str) and first_url.strip()
                else None
            )
            items.append((text.strip(), url))

        return items

    def _to_str_key_dict(self, value: object) -> dict[str, Any] | None:
        """Convert unknown object to dictionary with string keys."""
        if not isinstance(value, dict):
            return None

        return {
            key: item_value for key, item_value in value.items() if isinstance(key, str)
        }
