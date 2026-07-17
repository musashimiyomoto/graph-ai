"""Webhook dependency providers."""

from usecases import WebhookUsecase


def get_webhook_usecase() -> WebhookUsecase:
    """Return the public webhook use case."""
    return WebhookUsecase()
