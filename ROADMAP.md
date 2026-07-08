# Graph AI — Roadmap

Visual graph-based AI workflow builder (FastAPI + React + PostgreSQL). This document
tracks where the product is today and the prioritized plan to grow it — both new
capabilities and hardening of what already exists. There is no separate
breadth/depth split anymore: everything below is one prioritized list, verified
against the actual code as of this writing (not carried forward from stale notes).

## Where we are today

- **Backend** — layered `router → usecase → repository`, ARQ + Redis background
  execution, 8 entities (User, Workflow, Node, Edge, Execution, NodeExecution,
  LLMProvider, TelegramBot), JWT auth, encrypted secrets (Fernet), typed ports,
  workflow versioning, Telegram bot polling + reply integration.
- **Frontend** — React 19 + React Flow graph editor, catalog-driven node inspector
  and node-creation dialog, a unified Chat view (merged with what used to be a
  separate Executions history: per-turn version pill, timestamps, and a per-node
  "Details" expansion via a generic `OutputRenderer`), a single Settings modal
  (LLM Providers + Telegram Bots as tabs, on a shared `Modal` primitive).
- **Execution engine** (`backend/usecases/execution.py`) — 6 node types (`INPUT`,
  `LLM`, `WEB_SEARCH`, `TEMPLATE`, `HTTP_REQUEST`, `OUTPUT`), async execution with
  retries/backoff/reaper, wave-parallel scheduling, per-node result persistence
  (`node_executions`), SSE streaming with a polling fallback, workflow versioning
  with pinned reruns.
- **Integrations** — multi-provider LLM (Ollama/OpenAI/Anthropic/OpenAI-compatible)
  with token streaming; Telegram bots (per-user, encrypted token) that can trigger a
  workflow from an incoming message and receive the reply, including a manually
  pinned chat ID for non-Telegram-triggered runs.

## Key limitations driving priorities

1. **Multi-step operations aren't atomic** — a crash between two commits (e.g.
   register's user+provider, or execution create-then-enqueue) leaves orphaned state
   that nothing reaps.
2. **Per-attempt LLM streaming duplicates tokens to the client on retry.**
3. **No frontend tests**, no undo/redo/multi-select, no React Query — all data
   fetching is hand-rolled `useState`/`useEffect`.
4. **Timezone-less datetime columns**, and pinned reruns can't record
   per-node results for nodes that were since deleted.

---

## Phase 0 — Hygiene & foundation ✅ done

- [x] Fail-fast when default JWT secret / Fernet key is used outside `local`/`test`
      (`settings/environment.py`, `settings/auth.py`, `settings/encryption.py`).
- [x] Catch non-`BaseError` in `create_execution`, roll back, mark `FAILED`.
- [x] Structured logging with execution-id context.
- [x] Migrations run + checked in CI (`alembic upgrade head` + `alembic check`).

## Phase 1 — Asynchronous execution ✅ done

- [x] ARQ + Redis background execution; `POST /executions` returns `202` immediately.
- [x] Per-node result table (`node_executions`) + `GET /executions/{id}/nodes`,
      now actually consumed by the frontend (Chat view's per-turn "Details").
- [x] Per-node retries with backoff (retryable errors only) + per-node timeout.
- [x] Idempotent enqueue (`_job_id="execution:{id}"`); stuck-execution reaper cron.
- [x] Wave-parallel scheduling for independent branches, isolated sessions.
- [x] SSE streaming (`GET /executions/{id}/stream`) with a client-side polling
      fallback when the stream ends early or is unsupported.

## Phase 2 — Multi-provider LLM + secrets ✅ done

- [x] Fernet-encrypted, write-only `LLMProvider.api_key`; never returned in responses.
- [x] OpenAI / Anthropic / OpenAI-compatible clients alongside Ollama.
- [x] Per-node generation params (`temperature`, `max_tokens`, `top_p`), opt-in via
      the `optional_number` widget.
- [x] Token streaming provider → worker (Redis pub/sub) → SSE → frontend
      (`useExecutions.liveTokens`).

## Phase 3 — Richer graph & node types ✅ done

- [x] Typed ports (`PortType` = text/json/file/list) with edge-level compatibility
      checks (`ports_compatible`, currently exact-match only — the intended
      extension point for a future coercion table).
- [x] Prompt/Template and HTTP Request nodes; plugin-based node registration
      (`NodeDefinition` + `nodes/registry.py` — one module + one list entry per node).
- [x] Workflow versioning: each run snapshots the live graph
      (`workflow_versions`), pinned via `executions.version_id`, rerunnable by
      `version_id`. **Known gap:** a pinned rerun whose nodes were *deleted* (not
      edited) still can't record `node_executions` rows — `node_id` is a hard FK to
      the live `nodes` table (see Data layer, below).
- [x] **Telegram bot integration** (new since the last roadmap pass): per-user
      `TelegramBot` entity (encrypted token), Input node polls a bot for incoming
      messages via an ARQ cron (`poll_telegram_updates`, every 10s), Output node
      replies via the bot after execution finishes, with an optional pinned
      `telegram_chat_id` for manual (non-Telegram-triggered) runs. Field
      visibility (`visible_when`) is fully declarative — adding a future format
      doesn't require new frontend branches.
- [x] **Condition/Router node**: binary if/else branching (`NodeType.CONDITION`,
      `nodes/condition.py`) — evaluates `contains`/`equals`/`regex`/`not_empty`
      against upstream text and routes to a `true`/`false` output handle.
      Required real engine work: `NodeHandler.execute` now returns a
      `NodeExecutionResult(output, selected_handle)` instead of a bare string;
      edges carry an optional `source_handle` (new column + `NodeGraphSpec.
      output_handles`); the wave/serial schedulers propagate per-node
      liveness so only the taken branch executes — the other gets a
      `SKIPPED` `node_executions` row and is excluded from downstream
      `parent_values`, with a clear failure if no live path reaches OUTPUT.
      Frontend renders one named `Handle` per branch (`CustomNodes.tsx`) and
      threads `sourceHandle` through edge create/load
      (`useGraphState.ts`/`GraphCanvas.tsx`). `NodeFieldVisibility` gained a
      `not_equals` sibling to `equals` for the value field's visibility rule.
- [x] **Code/Transform node**: user-authored Python (`NodeType.CODE_TRANSFORM`,
      `nodes/code_transform.py`) run against `RestrictedPython`
      (`compile_restricted` + `safe_globals`/`safe_builtins` +
      `safer_getattr`/guarded getitem/getiter, plus a small extra-builtins
      allowlist including `json`) on a worker thread (`asyncio.to_thread`, so
      an infinite loop can't block the event loop — it does leak the thread,
      a known/documented limitation). Reads `input`, expects the script to
      assign `output`; non-string output is JSON-serialized. Syntax/runtime
      errors and a missing `output` assignment surface as
      `ExecutionGraphValidationError`.
- [x] **RAG / Vector search**: two node types, `Vector Ingest`
      (`nodes/vector_ingest.py`) and `Vector Search` (`nodes/vector_search.py`),
      backed by a new Qdrant service (`docker-compose.yml`) and local CPU
      embeddings via `fastembed` (`rag/embeddings.py`, no LLM provider needed).
      Ingest chunks the upstream text (fixed 800/100 char size/overlap,
      `rag/qdrant.py`), embeds, and upserts into a named collection
      (auto-created); Search embeds the upstream text as a query and returns
      the top-k matching chunks joined for downstream nodes (e.g. an LLM
      prompt). Collection names are free text, shared globally, no dedup on
      re-ingest — deliberately minimal for v1. **Known gap:** no way to feed
      a document in except pasting its text through an Input node (or
      fetching it via HTTP Request) — no file upload — tracked in Phase 6.

## Phase 4 — UX consolidation ✅ done

First pass:
- [x] Merged the standalone Executions history modal into Chat mode — one place
      to browse + interact with runs, with per-turn version/timestamp/duration and
      a per-node result breakdown (`ChatPanel.tsx`, `OutputRenderer.tsx`).
- [x] Consolidated Providers + Telegram Bots into one Settings modal
      (`SettingsModal.tsx`, vertical tabs) on a shared `Modal` primitive
      (`Modal.tsx`), replacing three separate header buttons and three
      hand-rolled modal shells.
- [x] Forward-compatible output rendering: `OutputRenderer` dispatches on
      `PortType`, degrading gracefully to plain text for `file`/`list` until a
      real node type produces them.
- [x] **Unified `InspectorPanel.tsx`/`CreateNodeDialog.tsx` field rendering**
      into one shared `NodeFieldsForm.tsx`: the widget set
      (`TextField`/`NumberField`/`SelectField`/`ProviderField`/`ModelField`/
      `TelegramBotField`/...), the visibility filter, and the `updateField`
      clear-on-hide logic now live in one place. `NodeFieldsForm` also owns
      the `useLlmProviders`/`useProviderModels`/`useTelegramBots` hook calls,
      so `InspectorPanel`'s three hand-rolled `useEffect` fetches (manual
      `cancelled` flags) are gone — both surfaces get the same data-fetching
      path `CreateNodeDialog` already used correctly. Generalized the old
      provider-branch special case (`updateField('model', '')` called
      manually alongside the provider change) into a `datasource.depends_on`
      clear rule, so any field whose data source depends on the one just
      changed resets automatically. Each caller still owns its own
      persistence/error timing (`InspectorPanel` autosaves and shows errors
      live; `CreateNodeDialog` validates on submit) — only rendering was
      unified, not that behavior.

Second pass (closed out everything remaining):
- [x] **Migrated `CreateNodeDialog` onto the shared `Modal`** — it was a
      standalone `fixed inset-0` div with no Escape/click-outside handling;
      now wrapped in `Modal.tsx` so it behaves consistently with
      `SettingsModal` (Escape or click-outside calls `onCancel`).
- [x] Added `role="dialog"`, `aria-modal`, and a Tab/Shift+Tab focus trap to
      `Modal.tsx`, plus focus-on-open (first focusable element, or the panel
      itself) and focus-restore-on-close.
- [x] Confirmed destructive single-click deletes: node/edge delete
      (`NodeContextMenu.tsx`'s "Delete" now becomes an inline "Confirm
      delete"/"Cancel" pair), LLM provider and Telegram bot delete
      (`ProviderSettings.tsx`/`TelegramSettings.tsx`, same `confirmDeleteId`
      inline ✓/✕ pattern already used for workflow delete in
      `WorkflowSidebar.tsx`).
- [x] De-duplicated `ACTIVE_STATUSES` — now a single exported const in
      `lib/types.ts`, imported by `useExecutions.ts` and `ChatPanel.tsx`
      instead of each declaring its own copy.
- [x] Chat's live view now shows only the Output node's streamed tokens
      (`findOutputNodeId`/`liveOutputText` in `ChatPanel.tsx`, resolved from
      `nodeMetaByNodeId`) instead of concatenating every node's tokens into
      one blob; auto-scroll now only fires when the scroll container is
      already within 120px of the bottom, so it no longer yanks the viewport
      away from history the user scrolled up to read.
- [x] Surfaced run-validity (`runDisabledReason`) in Build mode too — a small
      "Can't run: ..." pill floats over the canvas (`GraphCanvas.tsx`) once a
      workflow is selected, instead of only learning about it after switching
      to History/Chat.
- [x] Normalized network-level fetch failures to `ApiError` in `lib/api.ts`'s
      `request()` — the `fetch()` call is now wrapped in a try/catch that
      turns a raw `TypeError` (dropped connection, DNS, CORS, offline) into
      the same `{ message, status }` shape as an HTTP error response
      (`status: 0` for "no response received"), so error handlers only ever
      see one shape.
- [x] Dismissible/auto-expiring error banner (`AppShell.tsx`) — a ✕ button
      clears it immediately (`onDismissError`), and it now also auto-clears
      after 8s if left untouched, instead of staying up permanently.
- [x] Fixed clearing a required number field silently saving as `0` —
      `NumberField` (`NodeFieldsForm.tsx`) now keeps an explicitly cleared
      field as `''` instead of coercing it via `Number('') === 0`, so the
      existing `requiredError` check in `validateFields` (which already
      special-cased non-number values) correctly flags it instead of
      silently accepting zero.
- [x] Warn when a node references a since-deleted LLM provider/model (or
      Telegram bot) — `NodeFieldsForm.tsx`'s `referenceWarning` checks a
      saved id/name against the loaded provider/model/bot list once fetching
      has settled (`useProviderModels` gained a `loading` flag to make this
      race-free) and shows "no longer exists"/"no longer available" instead
      of just a blank dropdown with the dead id silently retained.

## Phase 5 — Security & data hardening ✅ done

- [x] **Rate limiting** on `/auth/login` and `/auth/register` — a fixed-window
      Redis counter (`api/dependencies/rate_limit.py`, `INCR`+`EXPIRE` per
      client IP) rejects with 429 past 10 login / 5 register attempts per
      60s. Reuses a new shared `redis.asyncio.Redis` client on `app.state`
      (separate from the ARQ pool) set up in `main.py`'s lifespan. Tests
      override the two `enforce_*_rate_limit` dependencies with a no-op by
      default (`tests/conftest.py`); a dedicated `test_rate_limit.py` spins up
      a real Redis container to verify the 429 actually fires.
- [x] **CORS middleware** with an explicit origin allowlist from settings
      (`settings/cors.py`, `CORS_ALLOWED_ORIGINS` — comma-separated, default
      `http://localhost:3000`), wired via `CORSMiddleware` in `main.py`.
      `allow_credentials=False` since auth is Bearer-token, not cookie-based.
- [x] **Password length bounds** on `UserCreate.password` — `min_length=8`,
      `max_length=72` (bcrypt silently truncates past 72 bytes).
- [x] **Registration doesn't leak account existence** — `UserAlreadyExistsError`'s
      message no longer says "already exists"; it's now the same generic
      wording regardless of *why* registration failed, mirroring how login
      never reveals whether the credentials failure was a bad email or a bad
      password.
- [x] **JWT hardening (part 1)** — access tokens now carry `iat`/`jti`
      (`usecases/auth.py::_create_access_token`), forward-compatible
      groundwork for a future refresh token + revocation list keyed on `jti`.
      **Still open:** the refresh token + revocation list itself; currently
      still a single 30-minute token with no way to log out server-side.
- [x] **Unit-of-work commits.** `BaseRepository`'s write methods (`create`,
      `create_many`, `update_by`, `delete_by`, `delete_all`) now `flush` instead
      of `commit` (`db/repositories/base.py`) — the caller decides when to
      finalize. Single-write usecase methods (workflow/node/edge/llm_provider/
      telegram_bot/user CRUD) got a mechanically relocated `session.commit()`
      right after the repository call — same timing as before, just owned by
      the usecase instead of the repository, since their writes are read by
      other sessions in near-real-time (SSE status polling, the Chat "Details"
      view) and can't be deferred. The two real multi-write bugs got genuine
      fixes: `AuthUsecase.register` now commits the new `User` and its default
      Ollama `LLMProvider` together, so a crash between the two rolls back to
      no user at all instead of a providerless one; `ExecutionUsecase.
      create_execution` now commits the `Execution` row (plus any
      `WorkflowVersion` snapshot) *before* calling `enqueue`, so a durably
      `CREATED` execution is never lost to a crash between the two writes.
      `_record_node_result` (a node's result + heartbeat bump) also now
      commits both together. Since a DB transaction can't span the Redis
      enqueue call, the remaining "committed but never enqueued" window is
      covered by extending the reaper: `reap_stuck_executions` gained a
      `re_enqueue` callback and now also re-enqueues (not fails) `CREATED`
      executions older than a new `STUCK_CREATED_TIMEOUT_SECONDS = 120`
      (`constants/execution.py`) — re-enqueuing is safe because ARQ's
      existing `_job_id=f"execution:{id}"` dedup makes a duplicate enqueue for
      an execution that's actually already running a no-op. `worker.py`'s
      cron function builds the real callback from `ctx["redis"]`.
- [x] **Timezone-aware datetime columns** — `db/models/base.py`'s shared
      `Base` now declares `type_annotation_map = {datetime:
      DateTime(timezone=True)}`, so every `Mapped[datetime]` column across
      all models (`users`/`workflows`/`workflow_versions`.created_at/
      updated_at, `executions`.started_at/finished_at/heartbeat_at,
      `node_executions`.started_at/finished_at) is `timestamptz` instead of a
      naive `timestamp` whose correctness silently depended on the DB
      session timezone matching the app's UTC assumption. Migration
      `6b2f9a4c1e73` reinterprets the existing naive values as UTC
      (`ALTER COLUMN ... USING col AT TIME ZONE 'UTC'`, metadata-only, no
      data rewrite); verified both directions against the real dev DB.
      `usecases/execution.py` no longer strips tzinfo off `datetime.now(tz=UTC)`
      before persisting — the tz-aware value round-trips correctly now, so
      the `.replace(tzinfo=None)` dance is gone from all 8 call sites (and
      the matching test fixtures in `test_execution.py`).
- [x] **Added missing unique constraints** — `edges(workflow_id,
      source_node_id, target_node_id)` and `llm_providers(user_id, name)` no
      longer allow silent duplicates. New domain errors
      (`EdgeAlreadyExistsError`, `LLMProviderAlreadyExistsError`, both 409)
      wrap the underlying `IntegrityError` at the usecase layer (with a
      `session.rollback()` first, same lesson as the `BaseError` rollback
      fix above) so the API returns a clean 409 instead of a raw 500.
- [x] **Decouple `node_executions` from live `nodes`** — `node_id` is no
      longer an enforced foreign key (`db/models/node_execution.py`,
      migration `8f3a5d1c7b92` drops `node_executions_node_id_fkey`); it's
      now a plain historical reference, so rerunning a pinned version whose
      node was since *deleted* (not edited) no longer fails to INSERT its
      result row, and deleting a node no longer collaterally destroys
      unrelated execution history via cascade. Two new denormalized columns,
      `node_type`/`node_label`, are captured at record time from the graph
      snapshot (`_record_node_result`/`_record_skip*` now take the full
      `NodeResponse` instead of a bare `node_id`) so a result stays
      meaningful even after the live node is gone — exposed through
      `NodeExecutionResponse` and used as ChatPanel's node-label fallback
      (`meta?.label ?? nodeResult.node_label ?? Node #id`) ahead of the
      already-existing raw-ID fallback. Verified both migration directions
      against the real dev DB, plus a new test
      (`test_run_pinned_version_survives_deleted_node`) that deletes a node
      and reruns its pinned version end-to-end.
- [x] **`BaseError` execution-failure path now rolls back the session** before
      marking `FAILED`, matching the generic-`Exception` branch beside it
      (`usecases/execution.py::run_execution`) — a poisoned transaction can
      no longer make the failure-status commit itself throw.
- [x] **Global node-output size cap** — `_truncate_for_storage`
      (`usecases/execution.py`, `MAX_NODE_OUTPUT_CHARS = 50_000` in
      `constants/execution.py`) caps every node's persisted
      `node_executions.output` with a visible `[truncated: N chars total]`
      marker, applied uniformly regardless of node type. Deliberately scoped
      to storage only — the in-memory value handed to downstream nodes (and
      the final `executions.output_data` the user actually sees) stays
      full-fidelity; HTTP node's separate 10k pipeline-level truncation is
      unrelated and untouched.
- [x] **Parallel wave partial-failure now aggregates all failures and writes
      SKIPPED rows for unreached nodes** — when multiple nodes in the same
      wave fail simultaneously, `_aggregate_wave_errors` combines every
      failure's message into the execution's overall error instead of
      surfacing one arbitrarily (`_handle_wave_failures`,
      `usecases/execution.py`). Nodes in waves the abort never reaches get a
      `SKIPPED` `node_executions` row instead of no row at all, so the UI
      can distinguish "failed" from "never ran". Applied the same "unreached
      nodes get SKIPPED" fix to the serial execution path too, since it had
      the identical gap (just without the "multiple simultaneous failures"
      nuance, since serial only ever runs one node at a time).
- [x] **LLM streaming retries no longer duplicate tokens to the client** — a
      new `token_reset` signal (`streaming/tokens.py::publish_token_reset`,
      threaded through `_NodeRunContext.token_reset_publisher`) fires right
      before a node's retry starts, publishing on the same Redis channel as
      token deltas. The SSE layer forwards it as a `{"type": "token_reset"}`
      frame; the frontend (`useExecutions.ts`) clears that node's
      `liveTokens` entry on receipt instead of letting the retry's deltas
      append after the failed attempt's partial text.
- [x] **Stuck-execution timeout is now heartbeat-based, not absolute start-age**
      — new `executions.heartbeat_at` column (migration
      `4d8c2f0a7e91`), seeded at claim time and bumped in
      `_record_node_result` every time a node completes.
      `reap_stuck_executions` now compares `heartbeat_at or started_at`
      against the cutoff, so a legitimately long multi-node run that's still
      making progress keeps refreshing its heartbeat and won't be reaped
      just for having run for a while.
- [x] **Readiness probe now checks Redis and Qdrant too** (previously only
      Postgres) **and returns 503 once any dependency is unhealthy** instead
      of always 200 (`usecases/health.py`, `api/routers/health.py`). Redis/
      Postgres/Qdrant clients are now dependency-injected
      (`api/dependencies/{redis,qdrant}.py`, `db.get_session_factory`) so
      tests can swap in fakes — matching the pattern already used for
      `queue.get_arq_pool`.
- [x] **Length/size bounds added**: `WorkflowCreate`/`WorkflowUpdate.name`
      (1-200 chars), `ExecutionInputPayload.value` (50k chars),
      `LLMProviderCreate`/`Update.name` (1-200 chars) and `.config` (10k
      chars serialized JSON, via a shared `_validate_config_size`
      field-validator), `UserCreate.password` (8-72 chars, see JWT/password
      item above).
- [x] **Untyped node fields now validated at save time** — new
      `ValidatorType.JSON` (`usecases/node.py::_validate_json_field`) checks
      HTTP node `headers` parses as JSON before the node saves, matching the
      handler's existing run-time check; LLM `system_prompt` gained
      `MIN_LENGTH: 0` (accepts empty, but now rejects a non-string value)
      matching its handler's existing type check. HTTP `body` deliberately
      left unconstrained — the handler never parses it as JSON (arbitrary
      request bodies: XML, form data, plain text are all valid), so forcing
      JSON there would have been a real regression, not a fix.
- [x] **Streaming no longer pins a pooled DB connection for the whole SSE
      lifetime** — `_pump_status` (`usecases/execution.py`) now opens/closes
      a short-lived session per status poll via a session factory
      (`db.get_session_factory`, added earlier for the health check) instead
      of holding one request-scoped session/connection for up to 15 minutes
      (`STREAM_MAX_ITERATIONS * STREAM_POLL_SECONDS`). The stream endpoint's
      upfront ownership check also moved onto its own short-lived session,
      dropping the plain `db.get_session` dependency from that route entirely.

## Phase 6 — Node handler depth (usability, not new node types) ✅ done

- [x] **"Web Search" isn't a real web search** — replaced the near-always-empty
      Instant Answer API with DuckDuckGo's HTML lite endpoint
      (`https://lite.duckduckgo.com/lite/`, needs a browser-like User-Agent or
      it serves a bot-check page instead of results). `nodes/web_search.py`
      parses the results page with a small `html.parser.HTMLParser` subclass
      that pairs each `result-link` title with its sibling `result-snippet`
      text and unwraps DuckDuckGo's `/l/?uddg=...` redirect to the real
      target URL, while skipping `<tr class="result-sponsored">` rows
      entirely so ads never leak into node output. Verified live against the
      real endpoint during development (real queries now return ~10 organic
      results with title/snippet/URL, vs. the old API's empty
      `AbstractText`/`RelatedTopics` for the same queries).
- [x] **HTTP node: unencoded `{{input}}` URL substitution** — added
      `render_input_url_encoded` (`nodes/rendering.py`) alongside the
      existing `render_input`: only the substituted upstream text is
      percent-encoded via `urllib.parse.quote`, so a value with spaces/`&`/`#`
      can no longer corrupt the surrounding URL's query-string structure
      (the rest of the template — scheme, path separators, literal `?`/`&`/`=`
      — is left untouched). `_read_url` in `nodes/http_request.py` now uses
      it. Response truncation now carries a visible
      `[truncated: N chars total]` marker (mirroring the same pattern
      `_truncate_for_storage` already uses for node output storage), and
      `{{input}}` now also renders inside header values (`_read_headers`),
      not just the URL/body. Content-type-aware truncation was considered
      and skipped — the node pipeline is text-only end to end, so there's no
      binary/structured-response path that character truncation could
      corrupt differently than it already does for text.
- [x] **Template node: single exact-match `{{input}}`** — `_PLACEHOLDER_PATTERN`
      (`nodes/rendering.py`) replaces the old literal `str.replace`: matching
      is now case-insensitive and tolerant of internal whitespace, so
      `{{ input }}`/`{{INPUT}}` substitute the same as `{{input}}` instead of
      silently passing through unrendered. Also added an indexed form,
      `{{input[N]}}` (0-based, same case/whitespace tolerance), to reference
      one live parent by its deterministic ascending-parent-id position
      instead of always getting every parent's output newline-joined; an
      out-of-range index raises `ExecutionGraphValidationError` rather than
      silently rendering empty. Both `render_input` and
      `render_input_url_encoded` share the one regex, so Template and HTTP
      Request (URL/headers/body) nodes picked up the fix and the new syntax
      together. `TemplateNodeHandler`'s field help text now documents
      `{{input[0]}}`/`{{input[1]}}` for multi-parent templates.
- [x] **Vector Ingest document intake (upload, browse/delete, dedup)** — every
      ingested chunk now carries a `source` payload field identifying its
      document (`rag/ingest.py::ingest_document`, shared by the node handler
      and the new upload endpoint); re-ingesting the same `(collection,
      source)` deletes the prior chunks before inserting the new ones
      (`rag/qdrant.py::delete_by_source`), so re-running a Vector Ingest node
      or re-uploading a file replaces instead of duplicating — including
      when the new version has fewer chunks than the old one. The node
      gained an optional `source` field (defaults to the node's label).
      **New "Vector Collections" Settings tab**
      (`VectorCollectionSettings.tsx`, alongside LLM Providers/Telegram
      Bots) lists every collection with its chunk count, expands to list
      each document (source + chunk count) with inline delete, whole-collection
      delete, and a file-upload form (`.pdf`/`.docx`/`.txt`/`.md`,
      `rag/documents.py::extract_text` via `pypdf`/`python-docx`, 20 MB cap)
      that ingests directly into any collection — bypassing the graph
      entirely, so a document no longer has to be pasted through an Input
      node. Backed by a new `/vector-collections` router (list/upload/
      delete-document/delete-collection, `api/routers/vector.py`,
      `usecases/vector.py`) — collections stay global/shared, matching the
      feature's existing design. `lib/api.ts`'s shared `request()` helper
      now skips forcing a JSON content-type when the body is `FormData`, so
      the upload call reuses the same auth/error-handling path as every
      other request instead of a bespoke fetch. Vector Ingest/Search node
      handler tests (previously the only RAG test coverage) extended with
      dedup-replace and multi-source coexistence cases; new
      `tests/test_api/test_vector.py` covers the router end to end against
      a shared in-memory `FakeQdrantClient` (`tests/fakes.py`) — no real
      Qdrant server or fastembed model download needed in CI.

## Phase 7 — Product breadth (parallel track)

- [ ] Undo/redo, copy-paste, multi-select, auto-layout in the graph editor.
- [ ] React Query in place of hand-rolled `useState`/`useEffect` data fetching.
- [ ] Workflow template library, JSON export/import, duplication.
- [ ] Frontend tests (Vitest + Testing Library) — currently zero.
- [ ] Multi-tenant quotas, audit log, cost observability (tokens/latency per run).
- [ ] Metrics (Prometheus) + error tracking (Sentry).

---

### North star

From a synchronous, single-user Ollama editor → an asynchronous, multi-provider,
multi-channel (chat + Telegram) orchestration platform with typed data, streaming,
and production-grade hardening — where the UI stays declarative and scales to new
node types and integrations without per-feature frontend rewrites.
