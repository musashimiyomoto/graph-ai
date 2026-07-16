"""Sentry initialization shared by the API and worker processes."""

import logging

import sentry_sdk

from settings import sentry_settings

logger = logging.getLogger(__name__)


def init_sentry(component: str) -> None:
    """Initialize Sentry for a process, or no-op when no DSN is configured.

    Both the API and the ARQ worker are separate processes and each must call
    this on startup. With no ``SENTRY_DSN`` set this is a silent no-op, so
    local/CI runs need no Sentry account.

    Args:
        component: A short tag identifying the process (``"api"``/``"worker"``)
            attached to every event, so errors can be filtered by origin.

    """
    if not sentry_settings.enabled:
        return

    sentry_sdk.init(
        dsn=sentry_settings.dsn,
        environment=sentry_settings.environment,
        traces_sample_rate=sentry_settings.traces_sample_rate,
    )
    sentry_sdk.set_tag("component", component)
    logger.info("Sentry initialized for %s", component)
