"""Outbound webhook integration unit tests."""

from typing import Any, ClassVar, Self

import httpx
import pytest

import integrations.webhook as webhook_integration
from exceptions import WebhookConnectionError
from integrations.webhook import send_webhook


class _FakeWebhookClient:
    """Async httpx stand-in recording JSON POST calls."""

    calls: ClassVar[list[tuple[str, dict[str, Any]]]] = []

    def __init__(self, **kwargs: object) -> None:
        """Accept httpx client options."""
        del kwargs

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager."""
        del args

    async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        """Record one POST and return a successful response."""
        self.calls.append((url, json))
        request = httpx.Request("POST", url)
        return httpx.Response(status_code=200, request=request)


async def _allow_url(_url: str) -> None:
    """Allow a URL through the SSRF guard."""


@pytest.mark.asyncio
async def test_send_webhook_posts_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delivery uses an HTTP JSON POST with the supplied payload."""
    _FakeWebhookClient.calls = []
    monkeypatch.setattr(webhook_integration, "blocked_url_reason", _allow_url)
    monkeypatch.setattr(webhook_integration.httpx, "AsyncClient", _FakeWebhookClient)
    payload = {"status": "success", "output": {"value": "done"}}

    await send_webhook("https://hooks.example.com/result", payload)

    if _FakeWebhookClient.calls != [("https://hooks.example.com/result", payload)]:
        pytest.fail(f"Unexpected webhook request: {_FakeWebhookClient.calls}")


@pytest.mark.asyncio
async def test_send_webhook_rejects_private_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSRF-blocked destinations fail before opening an HTTP client."""

    async def _block_url(_url: str) -> str:
        """Return a fixed SSRF rejection reason."""
        return "URL resolves to a private address"

    monkeypatch.setattr(webhook_integration, "blocked_url_reason", _block_url)

    with pytest.raises(WebhookConnectionError):
        await send_webhook("http://127.0.0.1/callback", {"status": "success"})
