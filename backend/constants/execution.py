"""Execution lifecycle constants."""

# Age, in seconds, after which a still-RUNNING execution is considered stuck
# (e.g. the worker crashed mid-run) and is reaped to FAILED.
STUCK_EXECUTION_TIMEOUT_SECONDS = 3600

# Server-Sent Events stream: interval between status polls and a hard cap on
# iterations so a stream cannot stay open indefinitely. The cap covers a
# long-running node (up to ~15 min); past it the stream emits an "expired"
# frame and the client resumes polling.
STREAM_POLL_SECONDS = 1.0
STREAM_MAX_ITERATIONS = 900

# Pagination defaults for growing list endpoints (executions, node results).
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
