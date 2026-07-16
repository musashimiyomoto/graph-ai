"""Prometheus metrics settings."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from settings.base import BaseSettings


class MetricsSettings(BaseSettings):
    """Configuration for Prometheus metrics exposure.

    Under gunicorn each worker is a separate process with its own metric
    registry; setting ``PROMETHEUS_MULTIPROC_DIR`` to a shared writable
    directory makes ``prometheus_client`` aggregate counters/histograms across
    all workers (and the ARQ worker, if it shares the dir) so ``/metrics``
    reports fleet-wide totals rather than one worker's slice.
    """

    model_config = SettingsConfigDict(env_prefix="prometheus_")

    multiproc_dir: str = Field(
        default="",
        validation_alias="PROMETHEUS_MULTIPROC_DIR",
        title="Shared dir for multiprocess metric aggregation (empty = single)",
    )

    @property
    def multiprocess(self) -> bool:
        """Whether multiprocess aggregation is configured."""
        return bool(self.multiproc_dir)


metrics_settings = MetricsSettings()
