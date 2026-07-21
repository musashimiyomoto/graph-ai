"""Schemas for artifact metadata and typed node-value envelopes."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enums import PortType


class ArtifactReferencePayload(BaseModel):
    """Artifact reference embedded in a typed node value."""

    artifact_id: int = Field(default=..., gt=0)
    mime_type: str = Field(default=..., min_length=1, max_length=255)
    size: int = Field(default=..., ge=0)
    checksum: str = Field(default=..., pattern=r"^[0-9a-f]{64}$")
    filename: str | None = Field(default=None, max_length=255)


class NodeValuePayload(BaseModel):
    """JSON representation of a runtime NodeValue."""

    kind: PortType
    value: Any = None
    artifact: ArtifactReferencePayload | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    """Tenant-safe artifact metadata returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., gt=0)
    filename: str
    mime_type: str
    size: int = Field(default=..., ge=0)
    checksum: str
    created_at: datetime
    expires_at: datetime | None


class ArtifactUploadResponse(BaseModel):
    """Upload result, including whether existing bytes were reused."""

    artifact: ArtifactResponse
    deduplicated: bool


class ArtifactDownloadResponse(BaseModel):
    """Short-lived signed artifact download URL."""

    url: str
    expires_at: datetime
