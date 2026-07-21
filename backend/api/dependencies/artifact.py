"""Artifact use case dependency provider."""

from artifacts import artifact_store
from settings import artifact_settings
from usecases import ArtifactUsecase


def get_artifact_usecase() -> ArtifactUsecase:
    """Build an artifact use case over the shared object-store client."""
    return ArtifactUsecase(store=artifact_store, settings=artifact_settings)
