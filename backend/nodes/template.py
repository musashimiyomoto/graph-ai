"""Prompt/template node handler."""

from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from nodes.base import NodeExecutionContext
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)

_PLACEHOLDER = "{{input}}"


class TemplateNodeHandler:
    """Handler for prompt/template nodes."""

    async def execute(self, context: NodeExecutionContext) -> str:
        """Render the template, substituting upstream text for the placeholder.

        Args:
            context: Node execution context.

        Returns:
            The rendered template text.

        Raises:
            ExecutionGraphValidationError: If the template is missing or empty.

        """
        template = context.node_data.get("template")
        if not isinstance(template, str) or not template:
            message = "Template node requires a non-empty template"
            raise ExecutionGraphValidationError(message=message)

        upstream = (
            "\n".join(context.parent_values)
            if context.parent_values
            else context.input_value
        )
        return template.replace(_PLACEHOLDER, upstream)


def _build_handler(deps: NodeHandlerDeps) -> TemplateNodeHandler:
    """Build a template node handler."""
    del deps
    return TemplateNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.TEMPLATE,
    label="Prompt / Template",
    icon_key="template",
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
                placeholder="Template label",
            ),
            default="Template node",
        ),
        NodeFieldSpec(
            name="template",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="Template",
                placeholder="Summarize the following:\n\n{{input}}",
                help="Use {{input}} where the upstream text should be inserted.",
            ),
            default="{{input}}",
        ),
    ),
    build_handler=_build_handler,
)
