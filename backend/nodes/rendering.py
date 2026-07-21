"""Shared text-rendering helpers for node handlers."""

import re
from urllib.parse import quote

from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext

# Matches {{input}}, {{ input }}, {{INPUT}}, and an indexed form
# {{input[N]}}/{{ INPUT[ 2 ] }} that references a single live parent by its
# deterministic (ascending parent-id) position instead of the joined text.
_PLACEHOLDER_PATTERN = re.compile(
    r"\{\{\s*input(?:\s*\[\s*(?P<index>\d+)\s*\])?\s*\}\}", re.IGNORECASE
)


def upstream_text(context: NodeExecutionContext) -> str:
    """Return the combined upstream text feeding a node.

    Args:
        context: Node execution context.

    Returns:
        Joined parent values, or the raw input value when there are no parents.

    """
    if context.parent_values:
        return context.joined_parent_text()
    return context.input_text


def _resolve_placeholder(match: re.Match[str], context: NodeExecutionContext) -> str:
    """Resolve one matched placeholder to its substitution text.

    Args:
        match: A match of `_PLACEHOLDER_PATTERN`.
        context: Node execution context.

    Returns:
        The single parent's value for an indexed placeholder, otherwise the
        combined upstream text.

    Raises:
        ExecutionGraphValidationError: If an indexed placeholder's index has
            no corresponding live parent.

    """
    index_text = match.group("index")
    if index_text is None:
        return upstream_text(context)

    index = int(index_text)
    if index >= len(context.parent_values):
        message = (
            f"Template references {{{{input[{index}]}}}}, but this node only "
            f"has {len(context.parent_values)} live parent value(s)"
        )
        raise ExecutionGraphValidationError(message=message)
    return context.parent_values[index].require_text()


def render_input(text: str, context: NodeExecutionContext) -> str:
    """Substitute ``{{input}}``/``{{input[N]}}`` placeholders with parent text.

    Matching is case-insensitive and tolerant of internal whitespace, so
    ``{{ input }}`` and ``{{INPUT}}`` are substituted the same as
    ``{{input}}`` instead of silently passing through unrendered.

    Args:
        text: Template text possibly containing one or more placeholders.
        context: Node execution context.

    Returns:
        The rendered text.

    """
    return _PLACEHOLDER_PATTERN.sub(
        lambda match: _resolve_placeholder(match, context), text
    )


def render_input_url_encoded(text: str, context: NodeExecutionContext) -> str:
    """Substitute placeholders for use inside a URL, percent-encoding values.

    Only each substituted value is percent-encoded — the rest of the
    template (scheme, path separators, `?`/`&`/`=` in the query string) is
    left untouched, so a value containing spaces, `&`, or `#` can't corrupt
    the surrounding URL structure.

    Args:
        text: URL template possibly containing one or more placeholders.
        context: Node execution context.

    Returns:
        The rendered URL.

    """
    return _PLACEHOLDER_PATTERN.sub(
        lambda match: quote(_resolve_placeholder(match, context), safe=""), text
    )
