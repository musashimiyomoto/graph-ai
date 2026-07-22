"""Channel catalog dependency provider."""

from usecases import ChannelUsecase


def get_channel_usecase() -> ChannelUsecase:
    """Return the channel catalog use case."""
    return ChannelUsecase()
