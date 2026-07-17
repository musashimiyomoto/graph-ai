"""Signed public webhook token helpers."""

from utils.public_tokens import build_public_token, parse_public_token

_TOKEN_CONTEXT = "workflow-webhook"  # noqa: S105 - domain separator, not a secret


def build_webhook_token(workflow_id: int) -> str:
    """Build a stable signed token for a workflow ID.

    Args:
        workflow_id: Workflow exposed through the public webhook endpoint.

    Returns:
        A URL-safe token containing the ID and its HMAC signature.

    """
    return build_public_token(workflow_id, context=_TOKEN_CONTEXT)


def parse_webhook_token(token: str) -> int | None:
    """Validate a signed webhook token and return its workflow ID.

    Args:
        token: Token supplied by the public webhook caller.

    Returns:
        The positive workflow ID, or ``None`` when the token is malformed or
        has an invalid signature.

    """
    return parse_public_token(token, context=_TOKEN_CONTEXT)


def build_webhook_path(workflow_id: int) -> str:
    """Return the public backend path for a workflow webhook."""
    return f"/webhooks/{build_webhook_token(workflow_id)}"
