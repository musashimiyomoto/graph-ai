"""Public web-chat dependency providers."""

from usecases import WebChatUsecase


def get_web_chat_usecase() -> WebChatUsecase:
    """Return the public web-chat use case."""
    return WebChatUsecase()
