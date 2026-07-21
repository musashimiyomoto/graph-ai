"""Webhook dependency providers."""

from usecases import WebhookInboundRequest, WebhookUsecase

__all__ = ["WebhookInboundRequest", "WebhookUsecase", "get_webhook_usecase"]


def get_webhook_usecase() -> WebhookUsecase:
    """Return the public webhook use case."""
    return WebhookUsecase()
