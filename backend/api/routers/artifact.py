"""Tenant-scoped workflow artifact API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import artifact, auth, db
from api.dependencies.pagination import Pagination, get_pagination
from schemas import (
    ArtifactDownloadResponse,
    ArtifactResponse,
    ArtifactUploadResponse,
    UserResponse,
)
from settings import artifact_settings

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.post(path="", status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    file: Annotated[UploadFile, File(description="Artifact bytes")],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        artifact.ArtifactUsecase,
        Depends(dependency=artifact.get_artifact_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> ArtifactUploadResponse:
    """Upload one immutable artifact, deduplicated by tenant and checksum."""
    content = await file.read(artifact_settings.max_upload_bytes + 1)
    return await usecase.upload(
        session=session,
        user_id=current_user.id,
        filename=file.filename,
        mime_type=file.content_type,
        content=content,
    )


@router.get(path="")
async def list_artifacts(
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        artifact.ArtifactUsecase,
        Depends(dependency=artifact.get_artifact_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
    pagination: Annotated[Pagination, Depends(dependency=get_pagination)],
) -> list[ArtifactResponse]:
    """List active artifacts owned by the current user."""
    return await usecase.list_artifacts(
        session=session,
        user_id=current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(path="/{artifact_id}/download")
async def get_artifact_download(
    artifact_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        artifact.ArtifactUsecase,
        Depends(dependency=artifact.get_artifact_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> ArtifactDownloadResponse:
    """Create a short-lived signed URL for an owned active artifact."""
    return await usecase.get_download(
        session=session,
        user_id=current_user.id,
        artifact_id=artifact_id,
    )


@router.delete(path="/{artifact_id}")
async def delete_artifact(
    artifact_id: Annotated[int, Path(gt=0)],
    session: Annotated[AsyncSession, Depends(dependency=db.get_session)],
    usecase: Annotated[
        artifact.ArtifactUsecase,
        Depends(dependency=artifact.get_artifact_usecase),
    ],
    current_user: Annotated[UserResponse, Depends(dependency=auth.get_current_user)],
) -> JSONResponse:
    """Delete one owned artifact and its stored object."""
    await usecase.delete(
        session=session,
        user_id=current_user.id,
        artifact_id=artifact_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"detail": "Artifact deleted"},
    )
