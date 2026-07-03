"""Shared text-rendering helpers for node handlers."""

from nodes.base import NodeExecutionContext

INPUT_PLACEHOLDER = "{{input}}"


def upstream_text(context: NodeExecutionContext) -> str:
    """Return the combined upstream text feeding a node.

    Args:
        context: Node execution context.

    Returns:
        Joined parent values, or the raw input value when there are no parents.

    """
    if context.parent_values:
        return "\n".join(context.parent_values)
    return context.input_value


def render_input(text: str, context: NodeExecutionContext) -> str:
    """Substitute the ``{{input}}`` placeholder with the upstream text.

    Args:
        text: Template text possibly containing ``{{input}}``.
        context: Node execution context.

    Returns:
        The rendered text.

    """
    return text.replace(INPUT_PLACEHOLDER, upstream_text(context))
