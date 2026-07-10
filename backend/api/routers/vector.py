"""Vector Collections API routes (browse/delete/upload documents)."""

from http import HTTPStatus
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, File, Form, Path, UploadFile, status
from fastapi.responses import JSONResponse

from api.dependencies import auth, queue, vector
from constants import MAX_DOCUMENT_UPLOAD_BYTES
from exceptions import BaseError, DocumentTooLargeError
from rag.jobs import read_ingest_job_status
from schemas import (
    UserResponse,
    VectorCollectionResponse,
    VectorDocumentResponse,
    VectorJobStatusResponse,
    VectorUploadJobResponse,
)

router = APIRouter(prefix="/vector-collections", tags=["Vector Collections"])


@router.get(path="")
async def list_vector_collections(
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[VectorCollectionResponse]:
    """List every Qdrant collection with its total chunk count."""
    del current_user
    return await usecase.list_collections()


@router.get(path="/{collection}/documents")
async def list_vector_documents(
    collection: Annotated[str, Path(description="Collection name")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> list[VectorDocumentResponse]:
    """List each document (source) in a collection with its chunk count."""
    del current_user
    return await usecase.list_documents(collection=collection)


@router.post(path="/{collection}/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_vector_document(
    collection: Annotated[str, Path(description="Collection name")],
    file: Annotated[UploadFile, File(description="Document to ingest")],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    source: Annotated[
        str | None,
        Form(description="Document identifier; defaults to the filename"),
    ] = None,
) -> VectorUploadJobResponse:
    """Accept a document and queue it for background ingestion.

    Text extraction and embedding are CPU-bound, so we hand the file to the ARQ
    worker and return immediately. The client polls ``GET /jobs/{job_id}`` to
    learn when ingestion finishes (or fails). The size cap is enforced here so a
    huge blob is rejected before it reaches Redis.
    """
    del current_user
    content = await file.read()
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise DocumentTooLargeError

    filename = file.filename or "upload"
    resolved_source = source.strip() if source and source.strip() else filename
    job = await pool.enqueue_job(
        "ingest_document_task", collection, filename, content, source
    )
    if job is None:  # only on a duplicate _job_id, which we never set
        message = "Could not queue the document for ingestion"
        raise BaseError(message=message, status_code=HTTPStatus.SERVICE_UNAVAILABLE)
    return VectorUploadJobResponse(job_id=job.job_id, source=resolved_source)


@router.get(path="/jobs/{job_id}")
async def get_vector_job_status(
    job_id: Annotated[str, Path(description="Background ingest job ID")],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> VectorJobStatusResponse:
    """Report the state of a background ingest job (processing/ready/failed)."""
    del current_user
    return await read_ingest_job_status(pool=pool, job_id=job_id)


@router.delete(path="/{collection}/documents/{source}")
async def delete_vector_document(
    collection: Annotated[str, Path(description="Collection name")],
    source: Annotated[str, Path(description="Document identifier")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete every chunk belonging to one document."""
    del current_user
    await usecase.delete_document(collection=collection, source=source)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Document deleted"}
    )


@router.delete(path="/{collection}")
async def delete_vector_collection(
    collection: Annotated[str, Path(description="Collection name")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete a collection outright."""
    del current_user
    await usecase.delete_collection(collection=collection)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Collection deleted"}
    )
