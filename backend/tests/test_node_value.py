"""Typed workflow node value tests."""

import pytest

from enums import PortType
from exceptions import ExecutionGraphValidationError
from nodes import ArtifactReference, NodeValue


def test_text_value_round_trips_through_typed_envelope() -> None:
    """Text stays lossless through the typed envelope."""
    value = NodeValue.text("hello", metadata={"source": "test"})

    if value.kind is not PortType.TEXT:
        pytest.fail(f"Unexpected kind: {value.kind}")
    if value.require_text() != "hello":
        pytest.fail("Text value did not round-trip")
    if value.to_payload() != {
        "kind": "text",
        "value": "hello",
        "artifact": None,
        "metadata": {"source": "test"},
    }:
        pytest.fail("Envelope payload did not preserve text metadata")


def test_json_and_list_keep_structured_payloads() -> None:
    """Structured inline values remain native in their envelopes."""
    json_value = NodeValue.json({"answer": 42})
    list_value = NodeValue.list(["a", 2, True])

    if json_value.to_payload()["value"] != {"answer": 42}:
        pytest.fail("JSON payload changed its structure")
    if list_value.to_payload()["value"] != ["a", 2, True]:
        pytest.fail("List payload changed its structure")


def test_text_handler_rejects_non_text_value() -> None:
    """Handlers cannot silently coerce structured values into text."""
    with pytest.raises(ExecutionGraphValidationError, match="Expected text"):
        NodeValue.json({"answer": 42}).require_text()


def test_media_value_carries_artifact_reference_without_inline_bytes() -> None:
    """Media envelopes point at stable artifact storage references."""
    artifact = ArtifactReference(
        artifact_id=1,
        mime_type="image/png",
        size=128,
        checksum="a" * 64,
        filename="screen.png",
    )
    value = NodeValue.artifact_value(PortType.IMAGE, artifact)

    if value.to_payload()["artifact"] != {
        "artifact_id": 1,
        "mime_type": "image/png",
        "size": 128,
        "checksum": "a" * 64,
        "filename": "screen.png",
    }:
        pytest.fail("Artifact metadata was not preserved")


def test_artifact_value_round_trips_through_persisted_payload() -> None:
    """A complete media envelope can be restored from JSONB-compatible data."""
    original = NodeValue.artifact_value(
        PortType.AUDIO,
        ArtifactReference(
            artifact_id=42,
            mime_type="audio/mpeg",
            size=4096,
            checksum="b" * 64,
            filename="voice.mp3",
        ),
        metadata={"source": "telegram"},
    )

    restored = NodeValue.from_payload(original.to_payload())

    if restored != original:
        pytest.fail("Persisted artifact envelope did not round-trip")


def test_artifact_kind_rejects_inline_data() -> None:
    """Binary kinds never carry bytes or base64 inline."""
    with pytest.raises(ValueError, match="require an artifact"):
        NodeValue(kind=PortType.FILE, value="base64-data")
