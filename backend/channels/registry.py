"""Single registration point for channel metadata and adapter capabilities."""

from channels.base import ChannelDefinition, ChannelSettingsSpec
from channels.email import EMAIL_ADAPTER
from channels.schedule import SCHEDULE_ADAPTER
from channels.telegram import TELEGRAM_ADAPTER
from channels.web_chat import WEB_CHAT_ADAPTER
from channels.webhook import WEBHOOK_ADAPTER
from enums import (
    ExecutionSource,
    InputNodeFormat,
    OutputNodeFormat,
    ValidatorType,
)
from schemas import (
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldVisibility,
    NodeFieldWidget,
)

_TELEGRAM_INPUT_FIELDS = (
    NodeFieldSpec(
        name="telegram_bot_id",
        required=False,
        validators={ValidatorType.GE.value: 1},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TELEGRAM_BOT,
            label="Telegram Bot",
            help="The bot to poll for messages.",
        ),
        datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.TELEGRAM_BOT),
    ),
)

_TELEGRAM_OUTPUT_FIELDS = (
    NodeFieldSpec(
        name="telegram_bot_id",
        required=False,
        validators={ValidatorType.GE.value: 1},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TELEGRAM_BOT,
            label="Telegram Bot",
            help="The bot to reply through.",
        ),
        datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.TELEGRAM_BOT),
    ),
    NodeFieldSpec(
        name="telegram_chat_id",
        required=False,
        validators={},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.OPTIONAL_NUMBER,
            label="Telegram Chat ID",
            help=(
                "Optional fixed destination for manual or cross-channel runs. "
                "Leave blank to reply to the triggering conversation."
            ),
            step=1,
        ),
    ),
)

_EMAIL_INPUT_FIELDS = (
    NodeFieldSpec(
        name="email_account_id",
        required=False,
        validators={ValidatorType.GE.value: 1},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.EMAIL_ACCOUNT,
            label="Email Account",
            help="The IMAP inbox to poll for incoming messages.",
        ),
        datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.EMAIL_ACCOUNT),
    ),
)

_EMAIL_OUTPUT_FIELDS = (
    NodeFieldSpec(
        name="email_account_id",
        required=False,
        validators={ValidatorType.GE.value: 1},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.EMAIL_ACCOUNT,
            label="Email Account",
            help="The SMTP account used to send the result.",
        ),
        datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.EMAIL_ACCOUNT),
    ),
    NodeFieldSpec(
        name="email_to",
        required=False,
        validators={ValidatorType.MIN_LENGTH.value: 0},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TEXT,
            label="To",
            placeholder="recipient@example.com",
            help=(
                "Optional fixed recipient. Leave blank to reply to the sender "
                "that triggered the run."
            ),
        ),
    ),
    NodeFieldSpec(
        name="email_subject",
        required=False,
        validators={ValidatorType.MIN_LENGTH.value: 0},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TEXT,
            label="Subject",
            placeholder="Workflow result",
            help="Optional fixed subject. Replies use the incoming subject when blank.",
        ),
    ),
)

_SCHEDULE_INPUT_FIELDS = (
    NodeFieldSpec(
        name="cron_expression",
        required=False,
        validators={ValidatorType.CRON.value: True},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TEXT,
            label="Schedule (cron)",
            placeholder="0 9 * * *",
            help="Standard 5-field cron expression, evaluated in UTC.",
        ),
    ),
    NodeFieldSpec(
        name="scheduled_value",
        required=False,
        validators={},
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TEXTAREA,
            label="Value",
            placeholder="latest AI news",
            help=(
                "A scheduled run has no incoming message, so this fixed text is "
                "used as its input. Leave blank to fire with an empty value."
            ),
        ),
        default="",
    ),
)

_WEBHOOK_OUTPUT_FIELDS = (
    NodeFieldSpec(
        name="webhook_url",
        required=True,
        validators={
            ValidatorType.MIN_LENGTH.value: 1,
            ValidatorType.URL.value: True,
        },
        ui=NodeFieldUI(
            widget=NodeFieldWidget.TEXT,
            label="Callback URL",
            placeholder="https://example.com/workflow-result",
            help="Public HTTP endpoint receiving the execution result as JSON.",
        ),
    ),
)

CHANNEL_DEFINITIONS: tuple[ChannelDefinition, ...] = (
    ChannelDefinition(
        source=ExecutionSource.MANUAL,
        label="Manual / Text",
        icon_key="input",
        input_format=InputNodeFormat.TXT,
        output_format=OutputNodeFormat.TXT,
        activity=False,
    ),
    ChannelDefinition(
        source=ExecutionSource.TELEGRAM,
        label="Telegram",
        icon_key="telegram",
        input_format=InputNodeFormat.TELEGRAM,
        output_format=OutputNodeFormat.TELEGRAM,
        activity=True,
        input_fields=_TELEGRAM_INPUT_FIELDS,
        output_fields=_TELEGRAM_OUTPUT_FIELDS,
        settings=ChannelSettingsSpec(
            key="telegram",
            label="Telegram Bots",
            component_key="telegram",
        ),
        receiver=TELEGRAM_ADAPTER,
        acknowledger=TELEGRAM_ADAPTER,
        deliverer=TELEGRAM_ADAPTER,
        poll_seconds=frozenset(range(0, 60, 10)),
    ),
    ChannelDefinition(
        source=ExecutionSource.SCHEDULE,
        label="Schedule",
        icon_key="schedule",
        input_format=InputNodeFormat.SCHEDULE,
        output_format=None,
        activity=True,
        input_fields=_SCHEDULE_INPUT_FIELDS,
        receiver=SCHEDULE_ADAPTER,
        acknowledger=SCHEDULE_ADAPTER,
        poll_seconds=frozenset(range(0, 60, 30)),
    ),
    ChannelDefinition(
        source=ExecutionSource.EMAIL,
        label="Email",
        icon_key="email",
        input_format=InputNodeFormat.EMAIL,
        output_format=OutputNodeFormat.EMAIL,
        activity=True,
        input_fields=_EMAIL_INPUT_FIELDS,
        output_fields=_EMAIL_OUTPUT_FIELDS,
        settings=ChannelSettingsSpec(
            key="email",
            label="Email Accounts",
            component_key="email",
        ),
        receiver=EMAIL_ADAPTER,
        acknowledger=EMAIL_ADAPTER,
        deliverer=EMAIL_ADAPTER,
        poll_seconds=frozenset(range(0, 60, 30)),
    ),
    ChannelDefinition(
        source=ExecutionSource.WEBHOOK,
        label="Webhook",
        icon_key="webhook",
        input_format=InputNodeFormat.WEBHOOK,
        output_format=OutputNodeFormat.WEBHOOK,
        activity=True,
        output_fields=_WEBHOOK_OUTPUT_FIELDS,
        receiver=WEBHOOK_ADAPTER,
        deliverer=WEBHOOK_ADAPTER,
    ),
    ChannelDefinition(
        source=ExecutionSource.WEB_CHAT,
        label="Web Chat",
        icon_key="chat",
        input_format=InputNodeFormat.WEB_CHAT,
        output_format=OutputNodeFormat.WEB_CHAT,
        activity=True,
        receiver=WEB_CHAT_ADAPTER,
    ),
)

_BY_SOURCE = {definition.source: definition for definition in CHANNEL_DEFINITIONS}
_BY_INPUT_FORMAT = {
    definition.input_format: definition
    for definition in CHANNEL_DEFINITIONS
    if definition.input_format is not None
}
_BY_OUTPUT_FORMAT = {
    definition.output_format: definition
    for definition in CHANNEL_DEFINITIONS
    if definition.output_format is not None
}

if set(_BY_SOURCE) != set(ExecutionSource):
    message = "Channel registry must define every execution source exactly once"
    raise RuntimeError(message)
if set(_BY_INPUT_FORMAT) != set(InputNodeFormat):
    message = "Channel registry must define every Input format exactly once"
    raise RuntimeError(message)
if set(_BY_OUTPUT_FORMAT) != set(OutputNodeFormat):
    message = "Channel registry must define every Output format exactly once"
    raise RuntimeError(message)


def get_channel_definition(source: ExecutionSource) -> ChannelDefinition:
    """Return one registered channel by execution source."""
    return _BY_SOURCE[source]


def get_output_channel(output_format: object) -> ChannelDefinition | None:
    """Resolve an Output-node format to its channel definition."""
    try:
        resolved = OutputNodeFormat(output_format)
    except ValueError:
        return None
    return _BY_OUTPUT_FORMAT.get(resolved)


def polling_channel_definitions() -> tuple[ChannelDefinition, ...]:
    """Return registered channels that own a polling schedule."""
    return tuple(
        definition
        for definition in CHANNEL_DEFINITIONS
        if definition.receiver is not None and definition.poll_seconds is not None
    )


def build_channel_fields(*, output: bool) -> tuple[NodeFieldSpec, ...]:
    """Build the format selector and gated fields for Input or Output nodes."""
    definitions = tuple(
        definition
        for definition in CHANNEL_DEFINITIONS
        if (definition.output_format if output else definition.input_format) is not None
    )
    formats = tuple(
        definition.output_format if output else definition.input_format
        for definition in definitions
    )
    format_values = [value.value for value in formats if value is not None]
    format_labels = {
        value.value: definition.label
        for definition, value in zip(definitions, formats, strict=True)
        if value is not None
    }
    default_format = OutputNodeFormat.TXT if output else InputNodeFormat.TXT
    result: list[NodeFieldSpec] = [
        NodeFieldSpec(
            name="format",
            required=True,
            validators={ValidatorType.SELECT.value: format_values},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Format",
                options=format_labels,
            ),
            default=default_format.value,
        )
    ]
    for definition, channel_format in zip(definitions, formats, strict=True):
        if channel_format is None:
            continue
        fields = definition.output_fields if output else definition.input_fields
        visibility = NodeFieldVisibility(field="format", equals=channel_format.value)
        result.extend(
            field.model_copy(update={"visible_when": visibility}) for field in fields
        )
    return tuple(result)
