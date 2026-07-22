"""Plugin-driven channel registry tests."""

import pytest

from channels import CHANNEL_DEFINITIONS
from channels.registry import build_channel_fields, polling_channel_definitions
from enums import ExecutionSource, InputNodeFormat, OutputNodeFormat


def test_registry_covers_sources_and_node_formats_once() -> None:
    """Every source and selectable Input/Output format has one plugin."""
    sources = [definition.source for definition in CHANNEL_DEFINITIONS]
    input_formats = [
        definition.input_format
        for definition in CHANNEL_DEFINITIONS
        if definition.input_format is not None
    ]
    output_formats = [
        definition.output_format
        for definition in CHANNEL_DEFINITIONS
        if definition.output_format is not None
    ]
    if set(sources) != set(ExecutionSource) or len(sources) != len(set(sources)):
        pytest.fail("Channel registry does not cover execution sources exactly once")
    if set(input_formats) != set(InputNodeFormat):
        pytest.fail("Channel registry does not cover Input formats")
    if set(output_formats) != set(OutputNodeFormat):
        pytest.fail("Channel registry does not cover Output formats")


def test_polling_plugins_implement_acknowledgement() -> None:
    """A polling receiver cannot expose a cursor it is unable to acknowledge."""
    pollers = polling_channel_definitions()
    if {definition.source for definition in pollers} != {
        ExecutionSource.TELEGRAM,
        ExecutionSource.EMAIL,
        ExecutionSource.SCHEDULE,
    }:
        pytest.fail("Unexpected polling channel set")
    if any(definition.acknowledger is None for definition in pollers):
        pytest.fail("Every polling channel must implement acknowledge")


def test_node_fields_and_labels_derive_from_registry() -> None:
    """Format choices and gated channel fields share registry metadata."""
    input_fields = build_channel_fields(output=False)
    output_fields = build_channel_fields(output=True)
    input_format = input_fields[0]
    output_format = output_fields[0]
    if input_format.validators["select"] != [item.value for item in InputNodeFormat]:
        pytest.fail("Input format choices diverged from channel registration order")
    if output_format.validators["select"] != [item.value for item in OutputNodeFormat]:
        pytest.fail("Output format choices diverged from channel registration order")
    if input_format.ui.options[InputNodeFormat.WEB_CHAT.value] != "Web Chat":
        pytest.fail("Input format label did not come from channel metadata")
    webhook_url = next(field for field in output_fields if field.name == "webhook_url")
    if webhook_url.visible_when is None or (
        webhook_url.visible_when.equals != OutputNodeFormat.WEBHOOK.value
    ):
        pytest.fail("Channel output field was not gated by its registered format")
