"""Signed public web-chat token helpers."""

from utils.public_tokens import build_public_token, parse_public_token

_TOKEN_CONTEXT = "workflow-web-chat"  # noqa: S105 - domain separator


def build_web_chat_token(workflow_id: int) -> str:
    """Build a stable web-chat token for a workflow."""
    return build_public_token(workflow_id, context=_TOKEN_CONTEXT)


def parse_web_chat_token(token: str) -> int | None:
    """Validate a web-chat token and return its workflow ID."""
    return parse_public_token(token, context=_TOKEN_CONTEXT)


def build_web_chat_path(workflow_id: int) -> str:
    """Return the public API base path for a workflow's web chat."""
    return f"/web-chat/{build_web_chat_token(workflow_id)}"
