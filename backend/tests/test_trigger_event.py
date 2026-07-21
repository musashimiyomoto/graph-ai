"""Universal trigger event contract tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from enums import ExecutionSource, PortType
from schemas import ArtifactReferencePayload, NodeValuePayload, TriggerEvent


def test_trigger_event_preserves_artifact_attachments() -> None:
    """Normalized messages and artifact references survive serialization."""
    checksum = "a" * 64
    event = TriggerEvent(
        channel=ExecutionSource.TELEGRAM,
        external_event_id="bot:1:update:42",
        message=NodeValuePayload(kind=PortType.TEXT, value="photo"),
        attachments=[
            NodeValuePayload(
                kind=PortType.IMAGE,
                artifact=ArtifactReferencePayload(
                    artifact_id=7,
                    mime_type="image/png",
                    size=123,
                    checksum=checksum,
                    filename="photo.png",
                ),
            )
        ],
        occurred_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    payload = event.model_dump(mode="json")
    if payload["attachments"][0]["artifact"]["checksum"] != checksum:
        pytest.fail("Trigger attachment metadata did not round-trip")
    if payload["raw_retention"] != "discard":
        pytest.fail("Raw provider payloads must be discarded by default")


def test_trigger_event_rejects_naive_timestamp() -> None:
    """Provider timestamps must retain an explicit timezone."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        TriggerEvent(
            channel=ExecutionSource.MANUAL,
            message=NodeValuePayload(kind=PortType.TEXT, value="hello"),
            occurred_at=datetime(2026, 7, 22, tzinfo=UTC).replace(tzinfo=None),
        )


def test_trigger_event_rejects_text_attachment() -> None:
    """The attachments list cannot silently carry ordinary message text."""
    with pytest.raises(ValidationError, match="artifact values"):
        TriggerEvent(
            channel=ExecutionSource.WEBHOOK,
            external_event_id="event-1",
            message=NodeValuePayload(kind=PortType.TEXT, value="hello"),
            attachments=[NodeValuePayload(kind=PortType.TEXT, value="not a file")],
            occurred_at=datetime(2026, 7, 22, tzinfo=UTC),
        )
