"""Tenant-safe knowledge collection routes."""

import json
from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from arq import ArqRedis
from fastapi import APIRouter, Body, Depends, File, Form, Path, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import auth, db, queue, vector
from constants import MAX_DOCUMENT_UPLOAD_BYTES
from exceptions import BaseError, DocumentTooLargeError
from rag.jobs import read_ingest_job_status
from schemas import (
    KnowledgeACL,
    KnowledgeIngestOptions,
    KnowledgeUploadTask,
    UserResponse,
    VectorCollectionResponse,
    VectorDocumentResponse,
    VectorJobStatusResponse,
    VectorSyncStateUpdate,
    VectorUploadJobResponse,
)

router = APIRouter(prefix="/vector-collections", tags=["Vector Collections"])


@router.get(path="")
async def list_vector_collections(
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> list[VectorCollectionResponse]:
    """List only the current tenant's logical knowledge collections."""
    return await usecase.list_collections(session=session, user_id=current_user.id)


@router.get(path="/{collection}/documents")
async def list_vector_documents(
    collection: Annotated[str, Path(description="Collection name")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> list[VectorDocumentResponse]:
    """List non-expired sources in one owned collection."""
    return await usecase.list_documents(
        session=session, user_id=current_user.id, collection=collection
    )


@router.post(path="/{collection}/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_vector_document(  # noqa: PLR0913
    collection: Annotated[str, Path(description="Collection name")],
    file: Annotated[UploadFile, File(description="Document to ingest")],
    pool: Annotated[ArqRedis, Depends(dependency=queue.get_arq_pool)],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    source: Annotated[
        str | None,
        Form(description="Document identifier; defaults to the filename"),
    ] = None,
    source_type: Annotated[
        str, Form(description="Connector/source adapter key")
    ] = "upload",
    external_id: Annotated[
        str | None, Form(description="Provider-native stable object ID")
    ] = None,
    revision: Annotated[
        str | None, Form(description="Provider revision for incremental sync")
    ] = None,
    acl_visibility: Annotated[
        str, Form(description="private or shared source visibility")
    ] = "private",
    acl_readers: Annotated[
        str | None, Form(description="Comma-separated reader principal IDs")
    ] = None,
    retention_days: Annotated[
        int | None, Form(description="Optional retention duration in days")
    ] = None,
    sync_cursor: Annotated[
        str | None, Form(description="Opaque incremental connector cursor")
    ] = None,
    metadata_json: Annotated[
        str | None, Form(description="Non-secret source metadata JSON object")
    ] = None,
    force: Annotated[  # noqa: FBT002
        bool, Form(description="Re-embed an unchanged revision")
    ] = False,
) -> VectorUploadJobResponse:
    """Accept a document and queue it for background ingestion.

    Text extraction and embedding are CPU-bound, so we hand the file to the ARQ
    worker and return immediately. The client polls ``GET /jobs/{job_id}`` to
    learn when ingestion finishes (or fails). The size cap is enforced here so a
    huge blob is rejected before it reaches Redis.
    """
    content = await file.read()
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise DocumentTooLargeError

    filename = file.filename or "upload"
    resolved_source = source.strip() if source and source.strip() else filename
    options = _knowledge_ingest_options(
        source_type=source_type,
        external_id=external_id,
        revision=revision,
        acl_visibility=acl_visibility,
        acl_readers=acl_readers,
        retention_days=retention_days,
        sync_cursor=sync_cursor,
        metadata_json=metadata_json,
        force=force,
    )
    await usecase.prepare_collection(
        session=session, user_id=current_user.id, name=collection
    )
    await session.commit()
    job_id = f"knowledge:{current_user.id}:{uuid4().hex}"
    task = KnowledgeUploadTask(
        owner_id=current_user.id,
        collection=collection,
        filename=filename,
        content=content,
        source=source,
        options=options,
    )
    job = await pool.enqueue_job(
        "ingest_document_task",
        task.model_dump(mode="python"),
        _job_id=job_id,
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
    """Report an owned background ingest job without cross-tenant probing."""
    if not job_id.startswith(f"knowledge:{current_user.id}:"):
        raise BaseError(
            message="Knowledge ingest job not found",
            status_code=HTTPStatus.NOT_FOUND,
        )
    return await read_ingest_job_status(pool=pool, job_id=job_id)


@router.delete(path="/{collection}/documents/{source}")
async def delete_vector_document(
    collection: Annotated[str, Path(description="Collection name")],
    source: Annotated[str, Path(description="Document identifier")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> JSONResponse:
    """Delete every chunk belonging to one document."""
    await usecase.delete_document(
        session=session,
        user_id=current_user.id,
        collection=collection,
        source=source,
    )
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
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> JSONResponse:
    """Delete a collection outright."""
    await usecase.delete_collection(
        session=session, user_id=current_user.id, collection=collection
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED, content={"detail": "Collection deleted"}
    )


@router.patch(path="/{collection}/sync-state")
async def update_vector_sync_state(
    collection: Annotated[str, Path(description="Collection name")],
    data: Annotated[VectorSyncStateUpdate, Body()],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
) -> VectorCollectionResponse:
    """Advance or clear an owned connector's opaque incremental cursor."""
    return await usecase.update_sync_state(
        session=session,
        user_id=current_user.id,
        collection=collection,
        data=data,
    )


def _knowledge_ingest_options(  # noqa: PLR0913
    *,
    source_type: str,
    external_id: str | None,
    revision: str | None,
    acl_visibility: str,
    acl_readers: str | None,
    retention_days: int | None,
    sync_cursor: str | None,
    metadata_json: str | None,
    force: bool,
) -> KnowledgeIngestOptions:
    """Parse bounded multipart metadata into the shared ingestion contract."""
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError as exc:
        raise BaseError(
            message="metadata_json must be a JSON object",
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc
    if not isinstance(metadata, dict) or len(json.dumps(metadata)) > 16 * 1024:
        raise BaseError(
            message="metadata_json must be a JSON object up to 16 KiB",
            status_code=HTTPStatus.BAD_REQUEST,
        )
    readers = acl_readers.split(",") if acl_readers else []
    try:
        return KnowledgeIngestOptions(
            source_type=source_type,
            external_id=external_id,
            revision=revision,
            acl=KnowledgeACL.model_validate(
                {"visibility": acl_visibility, "readers": readers}
            ),
            metadata=metadata,
            retention_days=retention_days,
            sync_cursor=sync_cursor,
            force=force,
        )
    except ValidationError as exc:
        raise BaseError(
            message="Invalid knowledge source metadata",
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc
