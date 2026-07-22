"""Channel catalog use case."""

from channels.registry import CHANNEL_DEFINITIONS
from schemas import (
    ChannelCapabilitiesResponse,
    ChannelCatalogItemResponse,
    ChannelSettingsResponse,
    NodeCatalogFieldResponse,
)


class ChannelUsecase:
    """Expose registered channel metadata to API consumers."""

    @staticmethod
    def get_catalog() -> list[ChannelCatalogItemResponse]:
        """Return channel metadata in deterministic registration order."""
        return [
            ChannelCatalogItemResponse(
                source=definition.source,
                label=definition.label,
                icon_key=definition.icon_key,
                input_format=definition.input_format,
                output_format=definition.output_format,
                activity=definition.activity,
                capabilities=ChannelCapabilitiesResponse(
                    receive=definition.receiver is not None,
                    acknowledge=definition.acknowledger is not None,
                    deliver=definition.deliverer is not None,
                ),
                poll_seconds=(
                    sorted(definition.poll_seconds)
                    if definition.poll_seconds is not None
                    else None
                ),
                settings=(
                    ChannelSettingsResponse(
                        key=definition.settings.key,
                        label=definition.settings.label,
                        component_key=definition.settings.component_key,
                    )
                    if definition.settings is not None
                    else None
                ),
                input_fields=[
                    NodeCatalogFieldResponse.model_validate(field)
                    for field in definition.input_fields
                ],
                output_fields=[
                    NodeCatalogFieldResponse.model_validate(field)
                    for field in definition.output_fields
                ],
            )
            for definition in CHANNEL_DEFINITIONS
        ]
