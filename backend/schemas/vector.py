"""Schemas for Vector Collections API responses."""

from typing import Literal

from pydantic import BaseModel, Field


class VectorCollectionResponse(BaseModel):
    """A Qdrant collection and how many chunks it holds."""

    name: str = Field(default=..., description="Collection name")
    point_count: int = Field(default=..., description="Total chunks stored", ge=0)


class VectorDocumentResponse(BaseModel):
    """A document (identified by `source`) and its chunk count."""

    source: str = Field(default=..., description="Document identifier")
    chunk_count: int = Field(
        default=..., description="Chunks stored for this document", ge=0
    )


class VectorUploadResponse(BaseModel):
    """Result of ingesting a document (the background job's own result shape)."""

    source: str = Field(default=..., description="Document identifier used")
    chunks_ingested: int = Field(
        default=..., description="Number of chunks stored", ge=0
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
