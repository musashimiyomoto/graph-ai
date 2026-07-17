"""Outbound webhook delivery integration."""

from typing import Any

import httpx

from constants import DEFAULT_TIMEOUT
from exceptions import WebhookConnectionError
from utils.network import blocked_url_reason


async def send_webhook(url: str, payload: dict[str, Any]) -> None:
    """POST an execution result to a configured public URL.

    Args:
        url: Destination callback URL.
        payload: JSON-serializable execution result metadata.

    Raises:
        WebhookConnectionError: If the URL is unsafe or the request fails.

    """
    reason = await blocked_url_reason(url)
    if reason is not None:
        raise WebhookConnectionError(message=reason)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise WebhookConnectionError(message="Webhook delivery timed out") from exc
    except httpx.HTTPStatusError as exc:
        message = f"Webhook returned {exc.response.status_code}"
        raise WebhookConnectionError(message=message) from exc
    except httpx.HTTPError as exc:
        raise WebhookConnectionError from exc
