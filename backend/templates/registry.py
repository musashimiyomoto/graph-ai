"""Template registry: the single registration point for workflow templates.

Mirrors nodes/registry.py's pattern — adding a template means declaring a
TemplateDefinition next to its graph and adding it to this list.
"""

from exceptions import WorkflowTemplateNotFoundError
from templates.api_watcher import DEFINITION as API_WATCHER_DEFINITION
from templates.approval_gate import DEFINITION as APPROVAL_GATE_DEFINITION
from templates.batch_summarizer import DEFINITION as BATCH_SUMMARIZER_DEFINITION
from templates.daily_digest import DEFINITION as DAILY_DIGEST_DEFINITION
from templates.definition import TemplateDefinition
from templates.document_ingest import DEFINITION as DOCUMENT_INGEST_DEFINITION
from templates.email_auto_responder import (
    DEFINITION as EMAIL_AUTO_RESPONDER_DEFINITION,
)
from templates.embeddable_web_chat import (
    DEFINITION as EMBEDDABLE_WEB_CHAT_DEFINITION,
)
from templates.rag_chatbot import DEFINITION as RAG_CHATBOT_DEFINITION
from templates.quick_translate import DEFINITION as QUICK_TRANSLATE_DEFINITION
from templates.simple_chatbot import DEFINITION as SIMPLE_CHATBOT_DEFINITION
from templates.support_ticket_router import (
    DEFINITION as SUPPORT_TICKET_ROUTER_DEFINITION,
)
from templates.telegram_echo_bot import DEFINITION as TELEGRAM_ECHO_BOT_DEFINITION
from templates.text_compactor import DEFINITION as TEXT_COMPACTOR_DEFINITION
from templates.weather_bot import DEFINITION as WEATHER_BOT_DEFINITION
from templates.webhook_telegram_alert import (
    DEFINITION as WEBHOOK_TELEGRAM_ALERT_DEFINITION,
)

TEMPLATE_DEFINITIONS: tuple[TemplateDefinition, ...] = (
    SIMPLE_CHATBOT_DEFINITION,
    EMBEDDABLE_WEB_CHAT_DEFINITION,
    RAG_CHATBOT_DEFINITION,
    DOCUMENT_INGEST_DEFINITION,
    TELEGRAM_ECHO_BOT_DEFINITION,
    EMAIL_AUTO_RESPONDER_DEFINITION,
    DAILY_DIGEST_DEFINITION,
    SUPPORT_TICKET_ROUTER_DEFINITION,
    BATCH_SUMMARIZER_DEFINITION,
    TEXT_COMPACTOR_DEFINITION,
    QUICK_TRANSLATE_DEFINITION,
    APPROVAL_GATE_DEFINITION,
    API_WATCHER_DEFINITION,
    WEBHOOK_TELEGRAM_ALERT_DEFINITION,
    WEATHER_BOT_DEFINITION,
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
