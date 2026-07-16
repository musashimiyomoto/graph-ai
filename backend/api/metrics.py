"""Prometheus metrics: registry, collectors, and the /metrics ASGI response.

Metrics are updated from two processes — the API (HTTP middleware) and the ARQ
worker (execution outcomes). When ``PROMETHEUS_MULTIPROC_DIR`` is set both write
to that shared directory and ``/metrics`` aggregates across them; otherwise a
single in-process registry is used (correct for a single-worker dev run).
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

from settings import metrics_settings

# Counters/histograms register on the default (global) registry. In
# multiprocess mode prometheus_client writes their samples to per-process
# files in PROMETHEUS_MULTIPROC_DIR; the /metrics collector below then merges
# them. In single-process mode the default registry is scraped directly.
http_requests_total = Counter(
    "graphai_http_requests_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "path", "status"),
)
http_request_duration_seconds = Histogram(
    "graphai_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
)
executions_total = Counter(
    "graphai_executions_total",
    "Total workflow executions finalized, by terminal status.",
    labelnames=("status",),
)
execution_duration_seconds = Histogram(
    "graphai_execution_duration_seconds",
    "Workflow execution wall-clock duration in seconds.",
)
execution_tokens_total = Counter(
    "graphai_execution_tokens_total",
    "Total LLM tokens consumed across workflow executions.",
)


def record_execution(status: str, duration_seconds: float, total_tokens: int) -> None:
    """Record one finalized execution's outcome, latency, and token cost.

    Called from the worker after a run finalizes. Safe to call whether or not
    multiprocess mode is configured.

    Args:
        status: Terminal execution status (e.g. ``"success"``/``"failed"``).
        duration_seconds: Wall-clock run duration.
        total_tokens: LLM tokens the run consumed.

    """
    executions_total.labels(status=status).inc()
    execution_duration_seconds.observe(duration_seconds)
    if total_tokens:
        execution_tokens_total.inc(total_tokens)


def render_latest() -> tuple[bytes, str]:
    """Render the current metrics snapshot as Prometheus exposition text.

    In multiprocess mode a fresh registry backed by a
    ``MultiProcessCollector`` merges every process's samples; otherwise the
    default global registry is scraped.

    Returns:
        A ``(payload, content_type)`` tuple for the HTTP response.

    """
    if metrics_settings.multiprocess:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
