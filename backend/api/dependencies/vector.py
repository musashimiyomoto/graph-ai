"""Vector Collections dependency providers."""

from typing import Annotated

from fastapi import Depends
from qdrant_client import AsyncQdrantClient

from api.dependencies.qdrant import get_qdrant_client
from usecases import VectorUsecase


def get_vector_usecase(
    client: Annotated[AsyncQdrantClient, Depends(dependency=get_qdrant_client)],
) -> VectorUsecase:
    """Get the Vector Collections usecase, bound to the request's Qdrant client.

    Args:
        client: Request-scoped Qdrant client.

    Returns:
        The Vector Collections usecase.

    """
    return VectorUsecase(client=client)
