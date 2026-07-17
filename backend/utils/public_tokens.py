"""Stable signed tokens for unauthenticated workflow product surfaces."""

import base64
import hashlib
import hmac

from settings import auth_settings


def build_public_token(workflow_id: int, *, context: str) -> str:
    """Build a URL-safe HMAC token scoped to one public feature.

    Args:
        workflow_id: Workflow exposed through a public endpoint.
        context: Domain separator preventing reuse across public features.

    Returns:
        The workflow ID and its signature as one stable token.

    """
    payload = str(workflow_id)
    message = f"{context}:{payload}".encode()
    digest = hmac.new(
        auth_settings.secret_key.encode(), message, hashlib.sha256
    ).digest()
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{payload}.{signature}"


def parse_public_token(token: str, *, context: str) -> int | None:
    """Validate a feature-scoped token and return its workflow ID."""
    try:
        raw_id, supplied_signature = token.split(".", maxsplit=1)
        workflow_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    if workflow_id <= 0:
        return None

    expected = build_public_token(workflow_id, context=context)
    _, expected_signature = expected.split(".", maxsplit=1)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    return workflow_id
