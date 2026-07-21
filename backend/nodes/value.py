"""Typed values exchanged between workflow node handlers."""

import json
from dataclasses import dataclass, field

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


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Stable reference to binary content managed by an artifact store.

    Phase 9's artifact-storage work will resolve ``artifact_id`` into a signed
    download. Defining the reference in the runtime envelope first keeps binary
    bytes out of worker messages and database text columns from the start.
    """

    artifact_id: str
    mime_type: str
    size: int
    checksum: str
    filename: str | None = None

    def __post_init__(self) -> None:
        """Validate artifact identity and metadata."""
        if not self.artifact_id.strip():
            msg = "Artifact reference requires a non-empty artifact_id"
            raise ValueError(msg)
        if not self.mime_type.strip():
            msg = "Artifact reference requires a non-empty MIME type"
            raise ValueError(msg)
        if self.size < 0:
            msg = "Artifact reference size cannot be negative"
            raise ValueError(msg)
        if not self.checksum.strip():
            msg = "Artifact reference requires a non-empty checksum"
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

    def to_legacy_text(self) -> str:
        """Serialize an inline value for existing text DB/API boundaries.

        This is an explicit compatibility boundary, not a port coercion. Artifact
        values cannot be represented safely until artifact persistence lands.
        """
        if self.kind is PortType.TEXT:
            return self.require_text()
        if self.kind in {PortType.JSON, PortType.LIST}:
            return json.dumps(self.value, ensure_ascii=False)
        raise ExecutionGraphValidationError(
            message=(
                f"Cannot serialize {self.kind.value} through a legacy text boundary"
            )
        )

    def to_payload(self) -> dict[str, JSONValue]:
        """Return a JSON-compatible representation of the complete envelope."""
        return {
            "kind": self.kind.value,
            "value": self.value,
            "artifact": self.artifact.to_payload() if self.artifact else None,
            "metadata": self.metadata,
        }


def _is_json_value(value: object) -> bool:
    """Return whether a value can be encoded as strict JSON."""
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True
