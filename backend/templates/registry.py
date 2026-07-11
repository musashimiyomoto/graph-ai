"""Template registry: the single registration point for workflow templates.

Mirrors nodes/registry.py's pattern — adding a template means declaring a
TemplateDefinition next to its graph and adding it to this list.
"""

from exceptions import WorkflowTemplateNotFoundError
from templates.definition import TemplateDefinition
from templates.rag_chatbot import DEFINITION as RAG_CHATBOT_DEFINITION
from templates.simple_chatbot import DEFINITION as SIMPLE_CHATBOT_DEFINITION
from templates.telegram_echo_bot import DEFINITION as TELEGRAM_ECHO_BOT_DEFINITION

TEMPLATE_DEFINITIONS: tuple[TemplateDefinition, ...] = (
    SIMPLE_CHATBOT_DEFINITION,
    RAG_CHATBOT_DEFINITION,
    TELEGRAM_ECHO_BOT_DEFINITION,
)

_DEFINITIONS_BY_KEY: dict[str, TemplateDefinition] = {
    definition.key: definition for definition in TEMPLATE_DEFINITIONS
}


def get_template_definition(key: str) -> TemplateDefinition:
    """Return the definition for a template key.

    Args:
        key: The template's stable identifier.

    Returns:
        The registered template definition.

    Raises:
        WorkflowTemplateNotFoundError: If the key is unregistered.

    """
    definition = _DEFINITIONS_BY_KEY.get(key)
    if definition is None:
        raise WorkflowTemplateNotFoundError
    return definition
