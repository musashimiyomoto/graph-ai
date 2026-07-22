"""Channel catalog API response schemas."""

from pydantic import BaseModel, Field

from enums import ExecutionSource, InputNodeFormat, OutputNodeFormat
from schemas.node import NodeCatalogFieldResponse


class ChannelSettingsResponse(BaseModel):
    """Frontend settings section exposed by a channel plugin."""

    key: str = Field(default=..., description="Stable settings section key")
    label: str = Field(default=..., description="Human-readable section label")
    component_key: str = Field(
        default=..., description="Frontend account form renderer key"
    )


class ChannelCapabilitiesResponse(BaseModel):
    """Adapter capabilities implemented by a channel plugin."""

    receive: bool
    acknowledge: bool
    deliver: bool


class ChannelCatalogItemResponse(BaseModel):
    """Declarative metadata for one registered channel."""

    source: ExecutionSource
    label: str
    icon_key: str
    input_format: InputNodeFormat | None
    output_format: OutputNodeFormat | None
    activity: bool
    capabilities: ChannelCapabilitiesResponse
    poll_seconds: list[int] | None = None
    settings: ChannelSettingsResponse | None = None
    input_fields: list[NodeCatalogFieldResponse] = Field(default_factory=list)
    output_fields: list[NodeCatalogFieldResponse] = Field(default_factory=list)
