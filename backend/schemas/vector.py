"""Schemas for tenant-safe knowledge collection and source APIs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_MAX_ACL_PRINCIPAL_LENGTH = 320


class KnowledgeACL(BaseModel):
    """Provider-neutral read visibility attached to every source revision."""

    visibility: Literal["private", "shared"] = "private"
    readers: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("readers")
    @classmethod
    def normalize_readers(cls, value: list[str]) -> list[str]:
        """Trim, bound, and deduplicate reader principal IDs."""
        normalized: list[str] = []
        for item in value:
            principal = item.strip()
            if not principal or len(principal) > _MAX_ACL_PRINCIPAL_LENGTH:
                message = "ACL readers must contain 1 to 320 characters"
                raise ValueError(message)
            if principal not in normalized:
                normalized.append(principal)
        return normalized


class KnowledgeIngestOptions(BaseModel):
    """Metadata and incremental-sync controls for one source ingestion."""

    source_type: str = Field(default="upload", pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    external_id: str | None = Field(default=None, max_length=1024)
    revision: str | None = Field(default=None, max_length=512)
    acl: KnowledgeACL = Field(default_factory=KnowledgeACL)
    metadata: dict = Field(default_factory=dict)
    retention_days: int | None = Field(default=None, ge=0, le=36500)
    sync_cursor: str | None = Field(default=None, max_length=2048)
    force: bool = False


class KnowledgeUploadTask(BaseModel):
    """Versionable owner-scoped payload passed to the ingestion worker."""

    owner_id: int = Field(gt=0)
    collection: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=512)
    content: bytes
    source: str | None = Field(default=None, max_length=512)
    options: KnowledgeIngestOptions = Field(default_factory=KnowledgeIngestOptions)


class VectorCollectionResponse(BaseModel):
    """An owner-visible collection backed by an opaque Qdrant namespace."""

    name: str = Field(default=..., description="Collection name")
    point_count: int = Field(default=..., description="Total chunks stored", ge=0)
    sync_cursor: str | None = None
    last_synced_at: datetime | None = None


class VectorDocumentResponse(BaseModel):
    """Durable metadata for one revisioned knowledge source."""

    source: str = Field(default=..., description="Document identifier")
    chunk_count: int = Field(
        default=..., description="Chunks stored for this document", ge=0
    )
    source_type: str
    external_id: str | None
    revision: str | None
    content_hash: str
    acl: KnowledgeACL
    metadata: dict
    expires_at: datetime | None
    last_synced_at: datetime


class VectorUploadResponse(BaseModel):
    """Result of ingesting a document (the background job's own result shape)."""

    source: str = Field(default=..., description="Document identifier used")
    chunks_ingested: int = Field(
        default=..., description="Number of chunks stored", ge=0
    )
    unchanged: bool = Field(
        default=False, description="Whether an identical revision skipped embedding"
    )


class VectorUploadJobResponse(BaseModel):
    """Acknowledgement that an upload was accepted for background ingestion."""

    job_id: str = Field(default=..., description="Background ingest job identifier")
    source: str = Field(default=..., description="Document identifier used")


class VectorJobStatusResponse(BaseModel):
    """Current state of a background ingest job."""

    status: Literal["processing", "ready", "failed"] = Field(
        default=..., description="Job lifecycle state"
    )
    chunks_ingested: int | None = Field(
        default=None, description="Chunks stored, once the job is ready", ge=0
    )
    detail: str | None = Field(
        default=None, description="Failure detail when the job failed"
    )


class VectorSyncStateUpdate(BaseModel):
    """Update an opaque connector cursor after a successful sync page."""

    sync_cursor: str | None = Field(default=None, max_length=2048)
