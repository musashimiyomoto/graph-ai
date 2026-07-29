"""Email auto-responder template: Input(email) -> LLM -> Output(email).

The account and LLM provider references are intentionally left unset. The user
selects them after creating the workflow. With no fixed recipient or subject,
the Output node replies to the sender and derives a conventional reply subject
from the incoming message.
"""

from enums import InputNodeFormat, NodeType, OutputNodeFormat, TemplateSettingsSection
from schemas import WorkflowGraphEdge, WorkflowGraphNode, WorkflowGraphTransfer
from templates.definition import TemplateDefinition

_GRAPH = WorkflowGraphTransfer(
    nodes=[
        WorkflowGraphNode(
            type=NodeType.INPUT,
            data={
                "label": "Support Inbox",
                "format": InputNodeFormat.EMAIL.value,
                "email_account_id": None,
            },
            position_x=0.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.LLM,
            data={
                "label": "Draft Reply",
                "llm_provider_id": None,
                "model": None,
                "system_prompt": (
                    "You are a helpful customer support assistant. Read the "
                    "incoming email, answer the sender's request clearly and "
                    "concisely, and do not invent details. Return only the email "
                    "body without a subject line."
                ),
            },
            position_x=280.0,
            position_y=0.0,
        ),
        WorkflowGraphNode(
            type=NodeType.OUTPUT,
            data={
                "label": "Email Reply",
                "format": OutputNodeFormat.EMAIL.value,
                "email_account_id": None,
                "email_to": "",
                "email_subject": "",
            },
            position_x=560.0,
            position_y=0.0,
        ),
    ],
    edges=[
        WorkflowGraphEdge(source_index=0, target_index=1, source_handle=None),
        WorkflowGraphEdge(source_index=1, target_index=2, source_handle=None),
    ],
)

DEFINITION = TemplateDefinition(
    key="email-auto-responder",
    name="Email Auto-Responder",
    description=(
        "Polls an inbox for new messages, drafts a support reply with an LLM, "
        "and emails it back to the sender. Pick an email account on the Input "
        "and Output nodes, and an LLM provider, after creating it."
    ),
    category="Channels",
    setup_steps=(
        "Add an inbox in Settings -> Email Accounts.",
        "Select the Support Inbox and Email Reply nodes and choose that account.",
        "Add an LLM provider in Settings -> LLM Providers, then select it on the Draft Reply node.",
    ),
    settings_sections=(
        TemplateSettingsSection.EMAIL,
        TemplateSettingsSection.PROVIDERS,
    ),
    graph=_GRAPH,
)
