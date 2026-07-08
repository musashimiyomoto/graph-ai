"""Schemas for Vector Collections API responses."""

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
    """Result of uploading and ingesting a document."""

    source: str = Field(default=..., description="Document identifier used")
    chunks_ingested: int = Field(
        default=..., description="Number of chunks stored", ge=0
    )
