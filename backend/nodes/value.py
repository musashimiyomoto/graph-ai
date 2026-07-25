"""Typed values exchanged between workflow node handlers."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from enums import PortType
from exceptions import ExecutionGraphValidationError

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]

_ARTIFACT_KINDS = {
    PortType.FILE,
    PortType.IMAGE,
    PortType.AUDIO,
    PortType.VIDEO,
}
_SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Stable reference to binary content managed by an artifact store.

    ``artifact_id`` resolves through the tenant-scoped artifact API into a
    short-lived signed download. Binary bytes never enter worker messages or
    database output columns.
    """

    artifact_id: int
    mime_type: str
    size: int
    checksum: str
    filename: str | None = None

    def __post_init__(self) -> None:
        """Validate artifact identity and metadata."""
        if self.artifact_id <= 0:
            msg = "Artifact reference requires a positive artifact_id"
            raise ValueError(msg)
        if not self.mime_type.strip():
            msg = "Artifact reference requires a non-empty MIME type"
            raise ValueError(msg)
        if self.size < 0:
            msg = "Artifact reference size cannot be negative"
            raise ValueError(msg)
        if len(self.checksum) != _SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in self.checksum
        ):
            msg = "Artifact reference requires a lowercase SHA-256 checksum"
            raise ValueError(msg)

    def to_payload(self) -> dict[str, JSONValue]:
        """Return a JSON-compatible representation of the reference."""
        return {
            "artifact_id": self.artifact_id,
            "mime_type": self.mime_type,
            "size": self.size,
            "checksum": self.checksum,
            "filename": self.filename,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ArtifactReference":
        """Validate and rebuild an artifact reference from persisted JSON."""
        artifact_id = payload.get("artifact_id")
        mime_type = payload.get("mime_type")
        size = payload.get("size")
        checksum = payload.get("checksum")
        filename = payload.get("filename")
        if (
            not isinstance(artifact_id, int)
            or not isinstance(mime_type, str)
            or not isinstance(size, int)
            or not isinstance(checksum, str)
            or not isinstance(filename, str | None)
        ):
            msg = "Persisted artifact reference has an invalid shape"
            raise TypeError(msg)
        return cls(
            artifact_id=artifact_id,
            mime_type=mime_type,
            size=size,
            checksum=checksum,
            filename=filename,
        )


@dataclass(frozen=True, slots=True)
class NodeValue:
    """A typed, serializable value passed through the execution graph.

    Text/JSON/list values are inline. File and media values carry only an
    ``ArtifactReference``; the artifact store owns their bytes. ``metadata`` is
    deliberately provider-neutral and is preserved for provenance and future
    named-port/schema work.
    """

    kind: PortType
    value: JSONValue = None
    artifact: ArtifactReference | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate that payload shape matches the declared kind."""
        if self.kind in _ARTIFACT_KINDS:
            if self.artifact is None or self.value is not None:
                msg = f"{self.kind.value} values require an artifact and no inline data"
                raise ValueError(msg)
        elif self.artifact is not None:
            msg = f"{self.kind.value} values cannot carry an artifact reference"
            raise ValueError(msg)

        if self.kind is PortType.TEXT and not isinstance(self.value, str):
            msg = "Text NodeValue requires a string"
            raise ValueError(msg)
        if self.kind is PortType.LIST and not isinstance(self.value, list):
            msg = "List NodeValue requires a list"
            raise ValueError(msg)
        if self.kind is PortType.JSON and not _is_json_value(self.value):
            msg = "JSON NodeValue requires JSON-compatible inline data"
            raise ValueError(msg)
        if not _is_json_value(self.metadata):
            msg = "NodeValue metadata must be JSON-compatible"
            raise ValueError(msg)

        # Detach top-level mutable containers supplied by callers. Deep values
        # remain JSON data and are serialized at every persistence boundary.
        if isinstance(self.value, list):
            object.__setattr__(self, "value", list(self.value))
        elif isinstance(self.value, dict):
            object.__setattr__(self, "value", dict(self.value))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def text(
        cls,
        value: str,
        *,
        metadata: dict[str, JSONValue] | None = None,
    ) -> "NodeValue":
        """Build an inline text value."""
        return cls(kind=PortType.TEXT, value=value, metadata=metadata or {})

    @classmethod
    def json(
        cls,
        value: JSONValue,
        *,
        metadata: dict[str, JSONValue] | None = None,
    ) -> "NodeValue":
        """Build an inline JSON value."""
        return cls(kind=PortType.JSON, value=value, metadata=metadata or {})

    @classmethod
    def list(
        cls,
        value: list[JSONValue],
        *,
        metadata: dict[str, JSONValue] | None = None,
    ) -> "NodeValue":
        """Build an inline list value."""
        return cls(kind=PortType.LIST, value=value, metadata=metadata or {})

    @classmethod
    def artifact_value(
        cls,
        kind: PortType,
        artifact: ArtifactReference,
        *,
        metadata: dict[str, JSONValue] | None = None,
    ) -> "NodeValue":
        """Build a file/media value from a stable artifact reference."""
        if kind not in _ARTIFACT_KINDS:
            msg = "artifact_value kind must be file, image, audio, or video"
            raise ValueError(msg)
        return cls(kind=kind, artifact=artifact, metadata=metadata or {})

    def require_text(self) -> str:
        """Return inline text or raise a graph validation error.

        Existing handlers all declare text ports, so receiving another kind is
        a graph/runtime contract violation rather than an implicit conversion.
        """
        if self.kind is not PortType.TEXT or not isinstance(self.value, str):
            raise ExecutionGraphValidationError(
                message=f"Expected text node value, received {self.kind.value}"
            )
        return self.value

    def to_payload(self) -> dict[str, JSONValue]:
        """Return a JSON-compatible representation of the complete envelope."""
        return {
            "kind": self.kind.value,
            "value": self.value,
            "artifact": self.artifact.to_payload() if self.artifact else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "NodeValue":
        """Validate and rebuild a typed value from a persisted envelope."""
        raw_kind = payload.get("kind")
        if not isinstance(raw_kind, str):
            msg = "Persisted node value is missing its kind"
            raise TypeError(msg)
        try:
            kind = PortType(raw_kind)
        except ValueError as exc:
            msg = f"Persisted node value has unsupported kind: {raw_kind}"
            raise ValueError(msg) from exc

        raw_metadata = payload.get("metadata", {})
        if not isinstance(raw_metadata, dict):
            msg = "Persisted node value metadata must be an object"
            raise TypeError(msg)
        raw_artifact = payload.get("artifact")
        if raw_artifact is not None and not isinstance(raw_artifact, dict):
            msg = "Persisted node value artifact must be an object"
            raise TypeError(msg)
        artifact = (
            ArtifactReference.from_payload(cast("dict[str, object]", raw_artifact))
            if raw_artifact is not None
            else None
        )
        value = payload.get("value")
        if not _is_json_value(value) or not _is_json_value(raw_metadata):
            msg = "Persisted node value contains non-JSON data"
            raise ValueError(msg)
        return cls(
            kind=kind,
            value=cast("JSONValue", value),
            artifact=artifact,
            metadata=cast("dict[str, JSONValue]", raw_metadata),
        )


def _is_json_value(value: object) -> bool:
    """Return whether a value can be encoded as strict JSON."""
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True
