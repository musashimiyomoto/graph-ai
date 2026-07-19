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
  and node-creation dialog, a Test Runs / Activity Log split (manual test runs vs.
  real Telegram traffic, sharing per-turn version pill/timestamps/a per-node
  "Details" expansion via a generic `OutputRenderer`), a single Settings modal
  (LLM Providers + Telegram Bots + Vector Collections as tabs, on a shared `Modal`
  primitive), React Query for list+CRUD data fetching, workflow export/import/
  duplicate + a global template library (Simple/RAG Chatbot, Telegram Echo Bot).
- **Execution engine** (`backend/usecases/execution.py`) — 6 node types (`INPUT`,
  `LLM`, `WEB_SEARCH`, `TEMPLATE`, `HTTP_REQUEST`, `OUTPUT`), async execution with
  retries/backoff/reaper, wave-parallel scheduling, per-node result persistence
  (`node_executions`), SSE streaming with a polling fallback, workflow versioning
  with pinned reruns.
- **Integrations** — multi-provider LLM (Ollama/OpenAI/Anthropic, with the OpenAI
  entry's base URL freely overridable for any OpenAI-API-compatible endpoint)
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
- [x] OpenAI / Anthropic clients alongside Ollama. The OpenAI client also
      serves any OpenAI-API-compatible endpoint — no separate provider type,
      just override the OpenAI entry's base URL.
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

## Phase 7 — Product breadth (parallel track) ✅ done

- [x] **Undo/redo, copy-paste, multi-select, auto-layout in the graph editor**
      — nodes/edges get server-assigned IDs (nothing client-generated), so
      undo/redo couldn't be a client-side snapshot diff; it's a stack of
      reversible commands (`useUndoRedo.ts`) that replay the same
      create/delete/update API calls, each command remembering its
      *current* server ID across redo cycles since a redone "create" gets a
      new one every time. `useGraphState.ts` builds a command after every
      structural mutation (create/delete/move node, create/delete edge,
      paste, auto-layout) and pushes it; deliberately does **not** cover
      Inspector field-data edits (label/config), which keep their existing
      autosave-on-change UX rather than sharing one linear undo stack with
      graph-shape changes. Multi-node delete needed one atomic batch
      command rather than N independently-composed per-node commands —
      undoing a delete of two nodes that were connected *to each other*
      requires recreating both nodes first (building a fresh
      original-id → new-id map) before recreating the edge between them,
      otherwise the second node's edge-recreation call references a
      already-stale, still-deleted id (`makeDeleteNodesCommand`; caught by
      the Playwright verification pass below, not by inspection). Deleting
      a node's edges relies on the existing DB `ON DELETE CASCADE` — undo
      is the only direction that needs to manually recreate them via
      `createEdge`. Multi-select and edge-select both come from React
      Flow's `onSelectionChange` (not each element's own `.selected`
      field) so one code path drives both `selectedNodeIds`/
      `selectedEdgeIds`; box-select is now plain left-drag
      (`selectionMode`/`selectionOnDrag`), panning moved to middle/
      right-mouse-drag (`panOnDrag={[1, 2]}`). Also fixed a related latent
      bug while wiring the Delete key: React Flow v11's own
      `deleteKeyCode` defaults to `'Backspace'`, and since `onNodesChange`
      was already wired to blindly `applyNodeChanges` (including `remove`
      changes), pressing Backspace with a node selected was silently
      deleting it from local visual state *without* calling the delete API
      — a pre-existing frontend/backend desync bug, now closed by setting
      `deleteKeyCode={null}` and routing Delete/Backspace through the new
      app-level keyboard handler (`App.tsx`) that properly calls the API
      and records an undo command. Copy-paste uses an in-memory clipboard
      (a ref, not the OS clipboard); paste remaps copied-internal-edges'
      endpoints through a fresh id map, same pattern as delete-undo.
      Auto-layout is a new `@dagrejs/dagre` dependency
      (`lib/autoLayout.ts`, `rankdir: 'LR'` to match the existing
      Input→...→Output convention), wired as one composite move-command so
      it's a single undo step. New toolbar buttons: Undo/Redo (disabled
      when the respective stack is empty)/Auto-layout
      (`AppShell.tsx`). Verified via a real headless-browser pass (not just
      lint/build): multi-select delete → undo → redo restores edges
      correctly, copy/paste, auto-layout → undo restores exact prior
      positions, box-select vs. right-drag-pan, toolbar buttons, and a
      page reload after each step confirming state actually persisted
      server-side rather than being a client-side illusion.
- [x] **React Query for simple list+CRUD data fetching** — `@tanstack/react-query`
      (`lib/queryClient.ts`, `QueryClientProvider` wired in `main.tsx`;
      `lib/queryKeys.ts` centralizes query keys). Migrated the 8 hooks that
      were plain list+CRUD (`useNodeCatalog`, `useLlmProviders`,
      `useProviderModels`, `useTelegramBots`, `useVectorCollections`,
      `useVectorDocuments`, and the list-half of `useWorkflowState`/
      `useActivityLog`) onto `useQuery`/`useMutation`, each mutation updating
      the shared cache via `setQueryData` instead of each hook instance
      holding its own local array. Real payoff: `NodeFieldsForm`'s provider/
      bot/collection pickers and the corresponding Settings tabs now read
      the *same* cached list — creating/deleting in Settings is instantly
      visible in the node inspector instead of each hook fetching
      independently. `useWorkflowState` split cleanly: the workflow list
      moved to `useQuery`, `activeWorkflowId` (pure UI selection, not server
      state) stayed a plain `useState`. `VectorCollectionSettings`'s
      remount-via-`key` trick for refreshing a collection's document list
      after upload was replaced with a targeted
      `queryClient.invalidateQueries` (the remount hack silently stopped
      refetching once RQ's `staleTime` made the remounted query resolve from
      cache instead of the network). **Deliberately left untouched**:
      `useExecutions.ts` (SSE token streaming + polling fallback merged into
      one `useState`), `useOllamaPull.ts` (SSE), `useVectorUploadJobs.ts`
      (hand-rolled job-status polling), and `useGraphState.ts`/
      `useUndoRedo.ts` (a replay-based undo/redo command stack, not a cache)
      — none of these are simple server-cache reads, so React Query would
      add risk without a real caching win.
- [x] **Workflow export/import, duplication, and a global template library**
      — all four share one portable graph shape (`WorkflowGraphTransfer`:
      nodes with no ID, edges referencing nodes by list *position* rather
      than a database ID, since a transferred graph always creates fresh
      nodes). New `WorkflowTransferUsecase` (`usecases/workflow_transfer.py`)
      composes the existing `WorkflowUsecase`/`NodeUsecase`/`EdgeUsecase` to
      build/rebuild a graph rather than duplicating their validation.
      **Export** (`GET /workflows/{id}/export`) scrubs account-private
      reference fields — `llm_provider_id`, `telegram_bot_id` — to `null`
      (matched by `NodeFieldDataSourceKind` in the node catalog, not
      hardcoded field names), since those IDs are meaningless outside the
      exporting account; plain-string datasource fields (`model`,
      `collection`) travel unscrubbed. **Import** (`POST /workflows/import`)
      rebuilds a workflow from that shape, validating every edge index is
      in-range *before* writing anything (creation isn't one DB transaction
      — each node/edge create commits on its own — so this avoids leaving an
      orphaned partial workflow behind for an error pure request data
      already reveals). **Duplicate** (`POST /workflows/{id}/duplicate`)
      reuses the same rebuild path but skips scrubbing (same account, so the
      references stay valid) and names the copy `"{name} (copy)"`.
      Required a real validation-layer change: `NodeUsecase._validate_node_field`
      gained `allow_unset_references` — a *required* field whose datasource
      kind is `LLM_PROVIDER`/`TELEGRAM_BOT`/`LLM_MODEL` (which depends on a
      provider being chosen) is allowed to stay `None` only when rebuilding
      a transferred graph, never through the public create/update-node API —
      the user fills these back in via the node inspector's existing
      "no longer exists" affordance, exactly as if the original provider had
      been deleted. **Template library** (`templates/` package, mirroring
      `nodes/registry.py`'s one-module-per-entry pattern; `GET
      /workflow-templates` + `POST /workflow-templates/{key}/instantiate`,
      reusing the import rebuild path) ships 3 presets: Simple Chatbot
      (Input→LLM→Output), RAG Chatbot (Input→Vector Search→LLM→Output —
      deliberately *no* Vector Ingest node, since ingesting on every chat
      turn would re-embed the same documents; populate the "documents"
      collection once via the existing Vector Collections upload UI first),
      and Telegram Echo Bot (Input(telegram)→LLM→Output(telegram)). All
      three ship with unset provider/bot references by design. Frontend:
      `WorkflowSidebar.tsx` gained Export/Duplicate per-workflow buttons, an
      Import file picker, and a "New From Template" button opening
      `NewFromTemplateDialog.tsx` (a `Modal.tsx` list, reusing
      `useWorkflowTemplates.ts`); `useWorkflowTransfer.ts` centralizes all
      four mutations and pushes newly-created workflows into the React
      Query workflow-list cache via `setQueryData` (same pattern Phase 7's
      React Query migration established) instead of a manual refetch.
      **Known gap / follow-up, not yet built:** every template today is a
      strictly linear input→...→output chain because the execution engine
      has no scheduling primitive for anything else — no loops (retry a
      sub-chain N times, iterate over a list), no fan-out/fan-in beyond the
      existing Condition node's single true/false branch, and no
      trigger/cron scheduling independent of a chat message or Telegram
      update. A template like "summarize each item in a list" or "poll an
      API every 5 minutes" isn't expressible yet. Unlocking richer templates
      needs engine work first, roughly in this order: (1) a loop/iteration
      node type (bounded — max-iterations cap, mirroring the existing
      `MAX_NODE_ATTEMPTS` retry cap — that fans a single upstream value out
      over a list and fans results back in, analogous to how Condition
      already diverges/reconverges the wave scheduler), (2) a scheduled
      (cron-style) trigger source alongside the existing Telegram-poll
      trigger, reusing `worker.py`'s existing ARQ cron registration pattern
      (`poll_telegram_updates`) rather than inventing a second scheduling
      mechanism, (3) then revisit the template catalog once those
      primitives exist — a "daily digest" or "batch summarizer" preset only
      makes sense after (1)/(2) land, not before. Design for (1) and (2)
      fleshed out below.
- [x] **Scheduled (cron) trigger** — a new `InputNodeFormat.SCHEDULE`
      alongside `TXT`/`TELEGRAM` (`enums/node.py`), reusing the existing ARQ
      cron pattern instead of inventing a second scheduling mechanism: a new
      `poll_scheduled_triggers` cron job in `worker.py` (ticking every
      30-60s, same idea as `_TELEGRAM_POLL_SECONDS`) finds Input nodes with
      `format=schedule`, decides whether they're due, and creates an
      execution via `ExecutionUsecase.create_execution` under a new
      `ExecutionSource.SCHEDULE` (`enums/execution.py`). Delivery is free:
      `_reply_via_telegram`'s existing pinned-`telegram_chat_id` fallback
      (`worker.py::_resolve_reply_chat_id`) already handles a non-Telegram
      trigger replying into a fixed chat, so a scheduled workflow with a
      Telegram Output node "just works" once the trigger exists. Open
      decisions before implementing: (1) plain interval ("every N minutes",
      zero new dependencies) vs. full cron syntax (day/hour precision like
      "daily digest at 9am", needs a new `croniter` dependency — not
      currently in `pyproject.toml`); (2) catch-up semantics if the worker
      was down past a scheduled fire — re-run once and resync vs. silently
      skip missed fires (leaning skip: avoids a burst of stacked LLM calls
      after an incident, unlike Telegram's offset-based catch-up, which is
      fine to replay); (3) where `last_fired_at` lives — directly on
      `node.data` (worker writes it via `NodeRepository.update_by`, same
      precedent as `TelegramBot.last_update_id`) vs. a dedicated
      `node_schedule_state` row, to avoid the worker mutating the same JSON
      blob the user edits from the inspector.
- [x] **Loop / iteration node** — one `NodeType.LOOP` node type supporting
      two modes (list-map and do-while-condition), with the loop body as a
      genuinely nested subgraph rather than an in-canvas cycle (the engine's
      `_topological_order` hard-rejects cycles today, and `outputs_by_node`/
      `node_executions` both assume one result per node per run). Design:
      - **Scoping**: a nullable self-referential `parent_node_id` on `Node`
        (FK to `nodes.id`, `ON DELETE CASCADE`) — `NULL` for the top-level
        graph, `<loop_node_id>` for nodes inside that loop's body. Plain
        `nodes`/`edges` rows, so CRUD, the field catalog, and
        `_snapshot_workflow`'s whole-workflow dump all keep working
        unchanged; only `_build_graph_context` needs to build per-scope
        (top level treats a Loop node as one atomic node; its body isn't
        part of the top-level adjacency at all).
      - **Two new leaf types**: `LOOP_INPUT`/`LOOP_OUTPUT` (bodies can't
        reuse top-level `INPUT`/`OUTPUT` — those carry a `format` concept
        like Telegram/schedule that's meaningless inside a loop iteration).
        Same "exactly one input/output" invariant as the top-level graph,
        just scoped.
      - **Execution**: Loop can't be a plain stateless `NodeHandler` like
        every other node — it needs to recursively call back into the graph
        runner (build the sub-graph, drive `_run_nodes_serial` over it,
        write `node_executions` for inner nodes). Special-cased directly in
        `ExecutionUsecase._run_node_once`/a new `_run_loop_node`, called out
        explicitly as an exception to the "one module + one registry entry"
        plugin pattern (`nodes/registry.py`), not a silent violation of it.
      - **List mode**: parses the upstream node's text as a JSON array (no
        new runtime list type — ports stay decl-time-only metadata, values
        stay `str` end to end, same precedent as Code/Transform already
        JSON-serializing non-string output); runs the body once per
        element, collects `LOOP_OUTPUT` results back into a JSON array as
        the Loop node's own output.
      - **Condition mode**: re-runs the body with each iteration's
        `LOOP_OUTPUT` feeding the next iteration's `LOOP_INPUT`; stop
        condition lives on the Loop node itself (reusing
        `ConditionNodeHandler`'s `_evaluate` logic, hoisted into a shared
        helper) rather than requiring a Condition node inside the body.
      - **Guardrails**: new `MAX_LOOP_ITERATIONS` constant
        (`constants/execution.py`, same spirit as `MAX_NODE_ATTEMPTS`) —
        list mode truncates with a visible marker past the cap (style of
        `_truncate_for_storage`), condition mode hard-stops and marks the
        result as "stopped: iteration cap" rather than failing the whole
        execution. Nested loops (a Loop inside a Loop body) explicitly
        disallowed in v1 via a create-time validation.
      - **Data model**: nullable `iteration` column on `node_executions`
        (`NULL` for top-level nodes, `0..N-1` inside a loop body); the Loop
        node itself still gets exactly one top-level result row.
      - **Frontend**: no nested React Flow canvas — double-click a Loop node
        switches `GraphCanvas.tsx` into a scoped view (parameterized by
        `parentNodeId`, same shape as the existing `workflow_id` param) with
        a breadcrumb back to the parent graph; `useGraphState.ts`/CRUD calls
        carry the scope, `useUndoRedo.ts` keeps working as the same linear
        command stack. `ChatPanel`/`OutputRenderer`'s per-node "Details"
        needs an iteration-grouped view (accordion of per-iteration node
        results) instead of the current flat one-result-per-node list.
      - **Build order**: data model + scoping + LOOP_INPUT/LOOP_OUTPUT types
        first (graph becomes buildable/validatable with no execution yet),
        then the recursive engine runner, then frontend scoped-canvas
        navigation, then iteration-grouped Details rendering — each is
        independently shippable.
- [x] **Frontend tests (Vitest + Testing Library)** — the first-ever frontend
      suite, since there were zero. Wired Vitest into the existing Vite config
      (a `test` block: `environment: 'jsdom'`, `globals: true`, a
      `src/test/setup.ts` importing `@testing-library/jest-dom/vitest`,
      `include: ['src/**/*.test.{ts,tsx}']`) rather than a separate config, plus
      `test`/`test:run` npm scripts, a `front-test` Make target, and a Test step
      in `.github/workflows/frontend.yml`'s lint job. Test files live beside
      their subjects under `src/`, so `tsc -b` (CI typecheck) and `eslint .`
      cover them too — they import the Vitest API explicitly (`import { describe,
      it, expect, vi }`) to satisfy strict TS + the browser-only eslint globals,
      no `any`. 50 tests across 8 files, weighted toward the highest-value pure
      logic: `lib/validation.ts` (`matchesVisibility` equals/not_equals/null;
      `validateFields` across required, the number/provider widget rules,
      `min_length`, `ge`/`le`, `select` membership, and the optional-empty
      skip), `lib/executionFormat.ts` (`formatDuration` ms/s/null/negative
      branches, `formatTime` invalid-date), `lib/autoLayout.ts` (empty input,
      left-to-right ordering, the center-preservation invariant, fallback sizes
      — against real `@dagrejs/dagre`, which is DOM-free), and
      `lib/api.ts`'s `request()` error normalization via `getWorkflows`/`login`
      with a stubbed `fetch` (success JSON, network-error `{status: 0}` shape,
      server `detail`/`statusText` fallback, JSON content-type + body, bearer
      injection). Plus `hooks/useUndoRedo.ts` via `renderHook` (push enables
      undo + clears the redo future, undo/redo move commands and fire the right
      callbacks, empty-stack no-op, `clear`) and two provider-free RTL component
      tests: `Modal.tsx` (dialog a11y attrs, Escape/click-outside → `onClose`,
      click-inside doesn't, first-focusable autofocus, Tab focus-trap wrap) and
      `OutputRenderer.tsx` (text, JSON pretty-print, malformed-JSON degrade to
      text, unknown/absent `PortType` fallback). Deliberately skipped the
      React-Flow canvas (needs measured DOM/ResizeObserver, brittle in jsdom)
      and React-Query-backed components (`NodeFieldsForm`, Settings tabs) —
      their pure logic (`validation.ts`) is tested directly instead of through a
      provider+api-mock render.
- [x] **Multi-tenant quotas, audit log, cost observability (tokens/latency per
      run)** — the tenant boundary is the `User` (no separate Org table), so
      everything keys off `user_id` (executions have no direct user column, so
      it's resolved from `workflow.owner_id`). **Cost capture** flows from the
      provider clients up: `stream_chat` now yields a `ChatStreamChunk`
      (text delta + a final `TokenUsage` frame) instead of a bare `str`, so the
      *streaming* worker path — not just the rarely-taken non-streaming `chat`
      path — captures tokens (OpenAI `stream_options={"include_usage": True}`,
      Anthropic `get_final_message().usage`, Ollama's terminal `done` line's
      `prompt_eval_count`/`eval_count`; each normalized into one `TokenUsage`
      shape). `NodeExecutionResult.usage` carries it back through
      `_NodeOutcome` into `_record_node_result`, which persists per-node
      `prompt_tokens`/`completion_tokens`/`total_tokens` (nullable — NULL for
      non-LLM node types, distinguishing "no LLM call" from "zero tokens");
      `_mark_execution_success`/`_failed` aggregate the run total via
      `NodeExecutionRepository.sum_tokens` onto matching `executions` columns
      (latency is derived from `finished_at - started_at`, no new column).
      **Quotas** are hybrid: a cheap Redis fixed-window counter
      (`api/dependencies/quota.py`, mirroring `rate_limit.py`, keyed by
      `(user, day)`) gates `POST /executions`, while `UsageUsecase.check_quota`
      re-checks the durable `usage_records` table (the source of truth) inside
      `create_execution` — so a lost/reset Redis counter can't let a tenant
      exceed the limit, and Telegram/schedule triggers that bypass the HTTP
      dependency are still bounded. Limits come from `settings/quota.py`
      (`QUOTA_MAX_EXECUTIONS_PER_DAY`/`QUOTA_MAX_TOKENS_PER_DAY`, both `0` =
      unlimited, so an unconfigured deploy behaves exactly as before). Usage is
      upserted (`INSERT … ON CONFLICT DO UPDATE`, race-safe) on run finalize,
      keyed by workflow owner. **Audit log** is an append-only `audit_logs`
      table; `AuditUsecase.record` stages a row on the caller's session (no
      commit — same transaction as the mutation it describes) from execution
      create and workflow/provider/bot create+delete. New `/usage` router:
      `GET /usage` (today's executions/tokens used + limit/remaining) and
      `GET /usage/audit` (paginated, tenant-scoped), both behind
      `get_current_user`. New `QuotaExceededError` (429). Migration
      `d7dc4089af97` adds the 6 token columns + the two tables; verified both
      directions against the real dev DB.
- [x] **Metrics (Prometheus) + error tracking (Sentry)** — Prometheus via
      `prometheus-client` (`api/metrics.py`): an HTTP middleware in `main.py`
      (after CORS) records `graphai_http_requests_total` +
      `graphai_http_request_duration_seconds` labeled by method and the matched
      *route template* (`request.scope["route"].path_format`, so per-id paths
      don't explode cardinality; `/metrics` itself is excluded from its own
      counters), and the worker records `graphai_executions_total` (by terminal
      status) / `graphai_execution_duration_seconds` /
      `graphai_execution_tokens_total` after each run finalizes. An
      unauthenticated `GET /metrics` router (like `health`) serves the
      exposition text; under gunicorn's multiple workers (plus the separate ARQ
      worker process) `PROMETHEUS_MULTIPROC_DIR` (`settings/metrics.py`) makes
      `prometheus_client` aggregate across processes via a
      `MultiProcessCollector`, else a single in-process registry is scraped
      (correct for a single-worker dev run). Sentry (`sentry-sdk[fastapi]`,
      `observability.py::init_sentry`, `settings/sentry.py`) initializes in
      **both** processes — `main.py` at import (`component="api"`) and
      `worker.py::startup` (`component="worker"`) — and is a **no-op when
      `SENTRY_DSN` is unset** (deliberately not fail-fast, unlike the
      auth/encryption secrets, so local/CI needs no Sentry account). New env
      vars documented in `.env.example`.

## Phase 8 — Product roadmap

Pending work is ordered by product value: flagship MVP capabilities first,
useful workflow extensions next, and routine or post-MVP improvements last.

- [x] **Embeddable web chat** — turn any workflow into a usable website chat
      widget with a public workflow-specific endpoint and streamed responses.
- [x] **Table node** — one consistent read-only node for public Google Sheets,
      CSV by URL, and PostgreSQL. It emits bounded `columns`/`rows` JSON for
      downstream nodes; PostgreSQL DSNs are encrypted, write-only settings and
      queries run in read-only transactions.
- [x] **Call Workflow node** — `NodeType.CALL_WORKFLOW` passes its upstream text
      into another workflow owned by the same user and returns that workflow's
      Output value inline, with direct/indirect recursion detection and a
      five-workflow nesting cap. The node catalog exposes a workflow picker
      (excluding the current workflow), and double-click navigation opens the
      called graph with breadcrumbs back to the caller. Execution versions now
      recursively embed the full called-workflow dependency graph, so queued and
      pinned runs remain reproducible if a called workflow is edited or deleted;
      legacy snapshots without embedded dependencies retain a live-graph fallback.
- [ ] **Execution cancellation** — stop queued or running workflow executions from
      the UI before they waste more time or tokens.
- [ ] **Approval node** — pause a workflow until a person approves or rejects the
      next step.
- [ ] **Switch node** — route a value into one of several named branches instead
      of the Condition node's binary true/false split.
- [ ] **MCP tool nodes** — connect workflows to capabilities exposed by MCP
      servers through explicit, visible graph nodes.
- [ ] **Session management** — keep users signed in with refresh tokens and let
      them securely log out or revoke active sessions.
- [ ] **Email verification and password recovery** — verify new accounts, reset a
      forgotten password, and change the current password from account settings.
- [ ] **Translate node** — translate upstream text into a selected target language;
      useful, but already achievable with the existing LLM node.
- [ ] **Delay / Wait node** — pause a branch for a duration or until a timestamp;
      primarily useful for longer-running automation beyond the initial MVP.
- [ ] **Vision support for the LLM node** — accept images for OCR, document review,
      screenshot analysis, and other multimodal workflows.
- [x] **Email channel** — incoming messages can trigger workflows through IMAP,
      and Email Output can deliver the result through SMTP.
- [x] **Email Auto-Responder template** — a ready-made
      `Email Input → LLM → Email Output` support workflow.
- [x] **Webhook channel** — workflows can be triggered through a signed public URL
      and can POST their result to a configured callback URL.

---

### North star

From a synchronous, single-user Ollama editor → an asynchronous, multi-provider,
multi-channel (chat + Telegram + email) orchestration platform with typed data,
streaming, and production-grade hardening — where the UI stays declarative and
scales to new node types and integrations without per-feature frontend rewrites.
