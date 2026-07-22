"""Channel catalog API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import channel
from schemas import ChannelCatalogItemResponse

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get(path="/catalog")
async def list_channel_catalog(
    usecase: Annotated[
        channel.ChannelUsecase,
        Depends(dependency=channel.get_channel_usecase),
    ],
) -> list[ChannelCatalogItemResponse]:
    """List registered channel metadata and adapter capabilities."""
    return usecase.get_catalog()
