"""Signed public webhook token helpers."""

import base64
import hashlib
import hmac

from settings import auth_settings

_TOKEN_CONTEXT = "workflow-webhook"  # noqa: S105 - domain separator, not a secret


def build_webhook_token(workflow_id: int) -> str:
    """Build a stable signed token for a workflow ID.

    Args:
        workflow_id: Workflow exposed through the public webhook endpoint.

    Returns:
        A URL-safe token containing the ID and its HMAC signature.

    """
    payload = str(workflow_id)
    message = f"{_TOKEN_CONTEXT}:{payload}".encode()
    digest = hmac.new(
        auth_settings.secret_key.encode(), message, hashlib.sha256
    ).digest()
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{payload}.{signature}"


def parse_webhook_token(token: str) -> int | None:
    """Validate a signed webhook token and return its workflow ID.

    Args:
        token: Token supplied by the public webhook caller.

    Returns:
        The positive workflow ID, or ``None`` when the token is malformed or
        has an invalid signature.

    """
    try:
        raw_id, supplied_signature = token.split(".", maxsplit=1)
        workflow_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    if workflow_id <= 0:
        return None

    expected_token = build_webhook_token(workflow_id)
    _, expected_signature = expected_token.split(".", maxsplit=1)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    return workflow_id


def build_webhook_path(workflow_id: int) -> str:
    """Return the public backend path for a workflow webhook."""
    return f"/webhooks/{build_webhook_token(workflow_id)}"
