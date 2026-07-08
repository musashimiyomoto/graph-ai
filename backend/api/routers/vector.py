"""Vector Collections API routes (browse/delete/upload documents)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile, status
from fastapi.responses import JSONResponse

from api.dependencies import auth, vector
from schemas import (
    UserResponse,
    VectorCollectionResponse,
    VectorDocumentResponse,
    VectorUploadResponse,
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


@router.post(path="/{collection}/documents")
async def upload_vector_document(
    collection: Annotated[str, Path(description="Collection name")],
    file: Annotated[UploadFile, File(description="Document to ingest")],
    usecase: Annotated[
        vector.VectorUsecase, Depends(dependency=vector.get_vector_usecase)
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    source: Annotated[
        str | None,
        Form(description="Document identifier; defaults to the filename"),
    ] = None,
) -> VectorUploadResponse:
    """Upload a document, extract its text, and ingest it into a collection."""
    del current_user
    content = await file.read()
    return await usecase.upload_document(
        collection=collection,
        filename=file.filename or "upload",
        content=content,
        source_override=source,
    )


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
