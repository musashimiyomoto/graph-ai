"""Execution lifecycle constants."""

# Age, in seconds, after which a still-RUNNING execution is considered stuck
# (e.g. the worker crashed mid-run) and is reaped to FAILED.
STUCK_EXECUTION_TIMEOUT_SECONDS = 3600

# Age, in seconds, after which a still-CREATED execution (never claimed by a
# worker — e.g. the enqueue call was lost after the DB commit) is re-enqueued.
# Much shorter than STUCK_EXECUTION_TIMEOUT_SECONDS: "never got picked up"
# should self-heal fast rather than wait an hour.
STUCK_CREATED_TIMEOUT_SECONDS = 120

# Server-Sent Events stream: interval between status polls and a hard cap on
# iterations so a stream cannot stay open indefinitely. The cap covers a
# long-running node (up to ~15 min); past it the stream emits an "expired"
# frame and the client resumes polling.
STREAM_POLL_SECONDS = 1.0
STREAM_MAX_ITERATIONS = 900

# Pagination defaults for growing list endpoints (executions, node results).
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Cap on a single node's persisted `node_executions.output` (storage only —
# does not affect the in-memory value fed to downstream nodes), so a giant
# scraped page or LLM response can't grow that table unbounded.
MAX_NODE_OUTPUT_CHARS = 50_000

# Cap on iterations a Loop node runs, in either mode — a huge upstream list
# (list mode) or a stop condition that never matches (condition mode) both
# stay bounded, same spirit as MAX_NODE_ATTEMPTS for per-node retries.
MAX_LOOP_ITERATIONS = 50

# Maximum number of workflows in one inline Call Workflow chain, including
# the root workflow. Prevents deeply nested but technically acyclic graphs
# from consuming a worker indefinitely.
MAX_WORKFLOW_CALL_DEPTH = 5

# A durable Delay node may release the worker for at most 30 days. This keeps
# accidentally-entered years or timestamps from leaving executions pending forever.
MAX_DELAY_SECONDS = 30 * 24 * 60 * 60
