# Graph AI — Roadmap

Visual graph-based AI workflow builder (FastAPI + React + PostgreSQL). This document
tracks where the product is today and the prioritized plan to grow it — both new
capabilities and hardening of what already exists. There is no separate
breadth/depth split anymore: everything below is one prioritized list, verified
against the actual code as of this writing (not carried forward from stale notes).

## Where we are today

- **Backend** — layered `router → usecase → repository`, ARQ + Redis background
  execution, durable workflow/node execution history and checkpoints, rotating
  browser sessions, email verification/password recovery, encrypted connection
  secrets, quotas/audit logs, workflow versioning, and tenant-owned LLM, Telegram,
  email, PostgreSQL, and MCP connection records.
- **Frontend** — React 19 + React Flow graph editor, catalog-driven node inspector
  and node-creation dialog, undo/redo/copy-paste/multi-select/auto-layout, scoped
  loop editing, a Test Runs / Activity Log split, per-node execution details,
  approval/delay/cancellation controls, React Query for CRUD data, connection
  settings, workflow transfer/duplication, an embeddable web chat, and a global
  library of 12 workflow templates.
- **Execution engine** (`backend/usecases/execution.py`) — 20 registered node types
  (including the two internal Loop boundary types), async execution with
  retries/backoff/reaper, wave-parallel scheduling and live branch propagation,
  nested loop bodies, durable approval/delay checkpoints, per-node result/token
  persistence, SSE token streaming, cancellation, and recursively pinned workflow
  versions for reproducible Call Workflow runs.
- **Integrations** — multi-provider LLM (Ollama/OpenAI/Anthropic, with the OpenAI
  entry's base URL freely overridable for any OpenAI-API-compatible endpoint)
  with token streaming; Qdrant/local embeddings; remote MCP tools; PostgreSQL,
  Google Sheets and CSV reads; Telegram, email, signed webhook and embeddable web
  chat channels; cron triggers; outbound webhooks; and Prometheus/Sentry
  observability.

## Key limitations driving priorities

1. **Typed runtime values are not yet persisted or exposed end to end.** Handlers
   and schedulers now exchange a tagged `NodeValue`, but every registered node
   still exposes text ports and existing DB/API boundaries deliberately serialize
   through the legacy text adapter. Artifact storage, envelope persistence and real
   JSON/file/media ports are the next steps before non-text values can survive
   checkpoints and travel through user-built graphs.
2. **Channels are not plugin-driven.** Input/Output expose a growing format enum,
   while Telegram/email/webhook polling and delivery are separate worker branches.
   Adding Slack, WhatsApp, Discord, or voice this way would multiply orchestration
   special cases instead of reusing one trigger/delivery contract.
3. **There is no durable conversation or workflow state across executions.** A
   channel can identify the triggering sender/thread, but a workflow cannot read or
   write scoped memory for that conversation, user, or workflow.
4. **Templates are static graphs with manual post-creation setup.** They cannot
   declare required connections/capabilities, guide configuration, ship sample
   input, validate readiness, or be saved/versioned by users.
5. **Vector collections are still global/shared.** They need tenant namespaces,
   source metadata and lifecycle/access controls before knowledge connectors can
   safely ingest from Drive, Notion, Confluence, or customer channels.

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

This phase contains the first product-expansion wave. Its remaining multimodal
item is promoted into the typed-artifact work in Phases 9–10 below rather than
being implemented as an image-only exception in the string runtime.

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
- [x] **Execution cancellation** — authenticated
      `POST /executions/{execution_id}/cancel` atomically moves only queued or
      running executions to the new terminal `CANCELLED` status (idempotent when
      already cancelled, `409` after success/failure), records completed-node
      token usage and an audit event once, then signals the matching ARQ job;
      workers have abort support enabled and cannot overwrite the durable
      cancelled state if cancellation races completion. SSE treats cancellation
      as terminal, and Test Runs exposes a `Cancel run` action with a distinct
      cancelled result state. Migration `f6b8c1d4e7a9` extends the shared
      PostgreSQL execution-status enum.
- [x] **Approval node** — a required-path `Approval` node durably checkpoints
      completed node results, moves the execution to `WAITING_APPROVAL`, and
      exposes its configured request plus upstream value in both Test Runs and
      Activity Log. Authenticated approve/reject endpoints lock the execution
      decision: approval marks the node successful and enqueues a continuation
      under a fresh ARQ job ID, restoring success/skipped checkpoints so earlier
      LLM/HTTP/side-effect nodes are not repeated; rejection finalizes the run as
      `REJECTED`, records usage and audit metadata, and sends no channel output.
      Pending approvals can also be cancelled. Approval nodes are top-level only
      and graph validation requires each one to lie on every input-to-output
      path, avoiding ambiguous concurrent pause/failure races. Migration
      `a7c9e2f4b6d8` adds the node/status enum values and execution checkpoint
      metadata.
- [x] **Switch node** — route upstream text by exact value into the first of
      1–8 ordered, named branches, with optional case sensitivity and a
      reserved `default` fallback. Branch names are validated as stable edge
      handles, node updates cannot remove or rename a handle while an edge is
      attached, and execution snapshots/checkpoint resumes preserve the same
      deterministic route. The inspector provides a structured branch editor
      and the canvas derives its output handles from persisted node data.
      Migration `b8d1f3a5c7e9` adds the node enum value.
- [x] **MCP tool nodes** — user-owned remote Streamable HTTP MCP servers are
      managed in Settings with SSRF-checked URLs and encrypted write-only HTTP
      headers. The `MCP Tool` node discovers the selected server's live tool
      catalog, accepts JSON arguments with `{{input}}`/`{{input[N]}}`
      substitution, invokes the tool through the official Python MCP SDK, and
      returns text or structured content to downstream nodes. Server references
      are ownership-validated and scrubbed during cross-account workflow
      transfer. Settings also includes a searchable official MCP Registry
      catalog with one-hour backend caching; active/latest Streamable HTTP
      entries expose a configure flow that resolves URL variables and
      secret headers before encrypted storage. Migration `c9e2a4f6b8d1` adds
      MCP server storage and the node enum value.
- [x] **Session management** — short-lived access JWTs now identify a
      persistent browser session and are kept only in frontend memory. Opaque
      refresh tokens live in rotating HttpOnly/SameSite cookies while only
      their SHA-256 hashes are stored server-side. Refresh restores login after
      reload and transparently retries an expired authenticated request;
      logout revokes the current session, and Settings lists active clients
      with last-used/IP metadata and per-session revocation that immediately
      invalidates its access tokens. Migration `d1f3a5c7e9b2` adds durable
      session storage.
- [x] **Email verification and password recovery** — new registrations now stay
      inactive until a one-time email link is consumed; only SHA-256 token hashes
      are stored in the new `auth_action_tokens` table, links expire, resends
      replace older links, and existing accounts are marked verified by migration
      to avoid lockout. Forgot-password and resend endpoints return the same
      generic response whether an account exists or not, while password reset and
      authenticated password change both revoke every browser session. Account
      mail is delivered through configurable SMTP (log-only in local/test), the
      auth screen handles verification/recovery links and resend flows, and the
      Settings modal now has one Account Security section for password changes and
      active-session management. Migration `e5b7c9d1f3a6` adds the verified-email
      timestamp and one-time token storage.
- [x] **Translate node** — translate upstream text into one of 18 target
      languages without consuming an LLM provider. The node auto-detects the
      source language and offers two no-key external services: Google's free
      (unofficial) web endpoint and MyMemory's public anonymous API. Each fixed
      endpoint has local request-size validation, strict response parsing, and
      retryable timeout/transport/provider failures; the inspector clearly
      discloses that text is sent to the selected third party and that free
      service limits apply. Migration `f7c9e1a3b5d8` adds the node enum value.
- [x] **Delay / Wait node** — pause execution for a relative duration
      (seconds/minutes/hours/days) or until an absolute timezone-aware ISO 8601
      timestamp, passing upstream text through unchanged. Waiting is a durable
      `WAITING_DELAY` checkpoint rather than an in-worker `sleep`: completed node
      results persist, the ARQ worker is released, and a fresh deferred job
      resumes from checkpoints at `wait_until`. Multiple Delay nodes reached in
      one parallel wave share the earliest pending wake-up and resume their due
      branches without duplicating earlier work; waits are capped at 30 days,
      remain cancellable, and the stuck-run reaper re-enqueues a due checkpoint
      if the Redis scheduling write was lost after the database commit. The UI
      exposes the pending timestamp/status in Test Runs, Activity Log, and node
      Details. Delay nodes are top-level only in v1 because loop iterations reuse
      a node ID and require a separate per-iteration continuation model.
      Migration `a1d3f5b7c9e2` adds the node/status enum values and durable
      wake-up timestamps.
- **Vision support for the LLM node** — promoted into Phase 10's Multimodal LLM
  node after Phase 9 makes images and other artifacts first-class graph values.
- [x] **Email channel** — incoming messages can trigger workflows through IMAP,
      and Email Output can deliver the result through SMTP.
- [x] **Email Auto-Responder template** — a ready-made
      `Email Input → LLM → Email Output` support workflow.
- [x] **Webhook channel** — workflows can be triggered through a signed public URL
      and can POST their result to a configured callback URL.

---

## Phase 9 — Typed values, artifacts, conversations, and connector foundation

This phase is the prerequisite for the next product wave. It deliberately builds
one reusable runtime contract for JSON, files, images, audio, channels, and state
instead of adding each new capability as a special case in `execution.py` or
`worker.py`. Work is ordered so each item can ship with backwards compatibility
for existing text-only workflow versions.

- [x] **First-class `NodeValue` envelope** — `nodes/value.py` now defines validated
      inline text/JSON/list values and file/image/audio/video values backed by an
      `ArtifactReference` (ID, MIME type, size, checksum, filename), with
      provider-neutral provenance metadata and JSON-compatible serialization.
      `NodeExecutionContext`, `NodeExecutionResult`, both schedulers, branch
      propagation, Call Workflow, Loop, retries and checkpoint restoration now
      exchange `NodeValue`; every existing text handler uses explicit text accessors
      and constructors, so a future structured value cannot be silently coerced.
      Current execution input/output and `node_executions.output` remain backward-
      compatible text boundaries through `NodeValue.to_legacy_text()` until the
      following artifact/persistence work lands. Added unit coverage for envelope
      validation, structured compatibility serialization, media references and
      non-text rejection; the complete 418-test backend suite remains green.
- [ ] **Artifact storage and lifecycle** — add an S3-compatible backend (MinIO in
      local Docker Compose), tenant-scoped upload/download APIs, signed short-lived
      URLs, content-addressed deduplication, quotas, retention and garbage
      collection. `node_executions` stores stable artifact references rather than
      database-sized blobs, and execution details render safe previews/downloads.
- [ ] **Real typed ports and explicit coercions** — allow definitions to expose
      typed named inputs/outputs, validate every edge against a small declared
      conversion table, and show inserted/required conversions in the editor.
      JSON/list values remain structured at runtime rather than being hidden in
      strings; lossy conversions are never implicit.
- [ ] **Multiple ordinary input/output handles** — generalize dynamic handles past
      routing nodes so Document AI can emit `text`/`tables`/`metadata`, Agent can
      emit `answer`/`trace`, and channel events can expose message/attachments
      without encoding everything into one payload. Snapshot, transfer, undo/redo,
      Call Workflow, Loop and checkpoint resume must preserve handle schemas.
- [ ] **Universal trigger event** — introduce a versioned `TriggerEvent` envelope
      containing channel, external event ID, sender, conversation/thread, locale,
      message, attachments, timestamp and provider-specific metadata. Every inbound
      adapter must be idempotent on the external event ID and retain the raw event
      only according to an explicit privacy/retention policy.
- [ ] **Plugin-driven channel registry** — define declarative channel/account
      metadata plus `receive`/`acknowledge`/`deliver` adapter contracts, moving
      Telegram/email/webhook behavior out of format-specific worker branches.
      Input/Output field definitions, Settings forms and activity-log labels derive
      from the same backend catalog, following the existing node registry pattern.
- [ ] **Durable conversations and scoped state** — add conversation/session records
      keyed by `(workflow, channel, external_thread)` and a typed state store with
      `execution`, `conversation`, `user` and `workflow` scopes, TTL, optimistic
      concurrency and audit history. Public web chat receives an opaque session ID;
      cross-channel identity linking stays opt-in.
- [ ] **Unified connections and OAuth foundation** — evolve one-off provider/bot/
      account settings toward a common encrypted Connection model supporting API
      keys, OAuth 2.0 authorization-code refresh, health checks, scopes, ownership,
      last-used metadata and revocation. Existing entities can remain compatibility
      facades until their adapters migrate.
- [ ] **Tenant-safe knowledge sources** — namespace Qdrant collections by owner,
      migrate existing collections without data loss, attach source/revision/ACL
      metadata, and add retention and incremental-sync primitives needed by Drive,
      Notion and Confluence connectors.
- [ ] **Artifact/channel safety and observability** — MIME sniffing, file-size and
      decompression limits, malware-scanner hook, SSRF/egress policy, per-connection
      rate limits, redacted logs, channel delivery attempts, artifact bytes and
      agent/tool costs in usage metrics and audit events.

## Phase 10 — Multimodal, agentic, and data node expansion

The first six items are the flagship set: together they unlock workflows that can
understand documents and media, act through tools, remember a conversation, and
return reliable structured results. The remainder broadens production use cases
without weakening determinism or side-effect controls.

- [ ] **Multimodal LLM** — extend the LLM node to accept text plus image/document/
      audio parts when the selected model supports them, advertise provider/model
      capabilities, reject unsupported combinations before execution, stream text
      normally, and record per-modality usage/cost. Covers screenshot analysis,
      visual question answering and document review without a separate Vision-only
      execution path.
- [ ] **Agent node** — run a bounded LLM → tool → observation loop over an explicit
      allowlist of MCP tools and Call Workflow targets. Persist a structured step
      trace, enforce step/time/token/cost limits, support cancellation and retries,
      and require Approval before configured side-effecting tools. Never allow an
      agent to discover or invoke an unapproved tenant connection implicitly.
- [ ] **Structured Output / Extract node** — produce JSON conforming to a user-
      supplied or UI-built JSON Schema, with deterministic validation, provider
      native structured-output mode when available, bounded repair retries and
      separate valid/error handles. Downstream JSON ports receive a real JSON value.
- [ ] **Memory / State node** — `get`, `set`, `append`, `delete` and semantic-search
      operations over Phase 9 scopes; configurable TTL and maximum history; atomic
      compare-and-set for counters/locks; clear provenance in execution details.
- [ ] **Document AI node** — extract text, layout, tables, key-value fields and page
      images from PDF/DOCX/scans, with OCR fallback and named outputs. Large jobs run
      asynchronously with progress events and reuse artifact checksums for caching.
- [ ] **Speech nodes** — Speech-to-Text with timestamps/language detection/speaker
      segments and Text-to-Speech with provider/voice selection and streamed audio
      artifacts, forming the media layer required by voice channels.
- [ ] **Image Generate / Edit node** — text-to-image, image-to-image, inpainting,
      size/quality/style controls, provider capability discovery, moderation and
      artifact outputs suitable for web, chat and CMS delivery.
- [ ] **Browser / Web Extract node** — fetch or render a page, select structured
      content, capture screenshots, and optionally execute a tightly bounded set of
      browser actions. Domain allowlists, private-network blocking, time limits,
      download limits and an Approval gate protect state-changing interactions.
- [ ] **Data Mapper node** — select, rename, filter and construct JSON using a safe
      declarative mapping language (JSONPath/JMESPath-class), replacing common
      Code/Transform scripts with previewable and schema-checkable transforms.
- [ ] **Merge / Join / Aggregate node** — deterministically combine parallel values
      through concat, zip, keyed join, object merge and aggregate modes, including
      explicit handling for missing/skipped branches and per-input named handles.
- [ ] **Database Action node** — parameterized INSERT/UPDATE/DELETE and stored-
      procedure calls on tenant connections, separated from the read-only Table
      node. Read-only preview, transaction boundaries, row caps, statement policy,
      idempotency keys and optional Approval are mandatory.
- [ ] **Guardrail node** — moderation, prompt-injection detection, PII/secret
      detection and redaction with pass/block/review handles, local rules where
      practical, explainable findings and configurable fail-open/fail-closed policy.
- [ ] **Evaluator / Judge node** — score relevance, groundedness, schema compliance,
      safety or a custom rubric; compare several candidate branches and select a
      winner while preserving every score for traces and regression datasets.
- [ ] **Cache / Deduplicate node** — exact or semantic cache with tenant/workflow
      scope, TTL and inspectable keys; event deduplication; cache-hit metadata; and
      explicit bypass/invalidation controls so side-effecting branches stay safe.
- [ ] **File Parse / Chunk node** — deterministic parsers and configurable semantic/
      fixed/heading-aware chunking with source/page metadata, making RAG ingestion
      an inspectable graph rather than a single fixed strategy hidden in Vector
      Ingest.

## Phase 11 — Channel and event expansion

Every integration below must use Phase 9's Connection, TriggerEvent and
ChannelAdapter contracts, support inbound and outbound delivery where the provider
allows it, preserve native conversation/thread IDs, ingest attachments as artifacts,
and expose delivery attempts in the activity log. Priority follows product impact,
not ease of adding an HTTP wrapper.

- [ ] **Slack** — app mentions, DMs, message shortcuts, reactions and file events;
      streamed/threaded replies, blocks, files and Approval actions in the source
      thread.
- [ ] **WhatsApp Business Cloud** — text, images, documents, locations, contacts and
      voice notes inbound; templates, interactive buttons/lists and media outbound;
      webhook signature verification and delivery/read status tracking.
- [ ] **Voice (Twilio/SIP)** — inbound/outbound calls, streaming STT → workflow → TTS,
      interruption/barge-in, call transfer, DTMF, recording consent and a hard
      latency/cost budget per call.
- [ ] **GitHub and GitLab** — issue, PR/MR, review, comment, push and pipeline events;
      comments/reviews, labels, statuses and check runs outbound, with installation-
      scoped permissions and repository allowlists.
- [ ] **Discord and Microsoft Teams** — DMs/channels, mentions, slash commands,
      threads and attachments; replies, cards/components and channel-aware rate
      limiting. Ship as separate adapters over the same contract.
- [ ] **Google Drive, Dropbox and OneDrive** — file create/update/delete triggers,
      incremental cursors, revision-aware artifact ingestion and optional generated-
      file output.
- [ ] **Notion and Confluence** — page/database/space change triggers, incremental
      knowledge sync, page creation/update and source ACL metadata preservation.
- [ ] **Jira and Linear** — issue create/update/comment triggers plus issue, comment,
      label, assignment and status actions suitable for support/incident templates.
- [ ] **SMS, push and calendar** — Twilio SMS and mobile/web push delivery; Google/
      Microsoft calendar event triggers and create/update/cancel actions with
      timezone-safe scheduling.
- [ ] **Event buses** — Kafka, NATS, RabbitMQ, SQS and Pub/Sub consumers/producers
      with durable cursors or acknowledgements, bounded concurrency, dead-letter
      routing, idempotency and trace/correlation propagation.

## Phase 12 — Use-case templates and template platform

Templates become guided, versioned product entry points rather than static graph
fixtures. A template is only shipped when its required nodes/channels exist and the
instantiated workflow can validate its setup before the first real event arrives.

- [ ] **Template manifest and setup wizard** — categories/tags/search, preview graph,
      required capabilities and connections, setup fields, sample input/expected
      output, readiness checks, secret/reference binding and a test-run checklist.
- [ ] **User/team templates** — save any workflow as a private template, version it,
      duplicate/share it inside a tenant, export/import it safely, and show a diff
      before applying an upstream template update. Public/community publishing and
      ratings remain a separate moderated follow-up.
- [ ] **Invoice Processing Autopilot** — Email/Drive attachment → Document AI →
      Structured Output → duplicate/policy checks → Approval → Database/ERP action.
- [ ] **Multimodal Support Desk** — WhatsApp/Slack message plus screenshot →
      Multimodal LLM + knowledge search → classification → Jira/Linear → threaded
      response, with escalation through Guardrail/Approval.
- [ ] **Voice Receptionist** — phone call → Speech-to-Text → Agent with calendar/CRM
      tools → appointment booking → Text-to-Speech → SMS confirmation.
- [ ] **AI Pull Request Reviewer** — GitHub/GitLab event → diff/context tools →
      parallel security/style/test evaluators → Merge → Approval → native review.
- [ ] **Incident Response Copilot** — PagerDuty/Alertmanager-style webhook → logs/
      metrics tools → root-cause hypotheses → Slack/Teams war room → Jira incident,
      with remediation tools always behind Approval.
- [ ] **Meeting to Actions** — audio/recording → transcription → summary + structured
      action extraction → Jira/Linear/Calendar assignments → email/chat recap.
- [ ] **Research Swarm** — schedule → parallel search/browser branches → per-source
      extraction/summaries → deduplication → evaluator/judge → cited Slack/email
      digest with source artifacts retained.
- [ ] **Lead Qualification Agent** — web form/WhatsApp → enrichment tools → structured
      score → Switch → CRM update, owner notification and calendar invitation.
- [ ] **Content Studio** — brief → research → draft variants → image generation →
      brand/safety evaluator → Approval → CMS/social delivery.
- [ ] **Knowledge Base Sync** — Drive/Notion/Confluence changes → parse → deduplicate
      → chunk → tenant vector collection → stale-source cleanup and sync report.
- [ ] **E-commerce Concierge** — web chat/WhatsApp plus product photo → visual and
      catalog search → recommendation Agent → inventory/order tools → rich reply.
- [ ] **Compliance Document Reviewer** — file upload → OCR/layout extraction → clause
      schema → policy RAG → risk evaluator → human review → annotated report.

---

### North star

From a synchronous, single-user Ollama editor → an asynchronous, multimodal,
multi-provider and multi-channel orchestration platform where durable workflows can
understand text/media/documents, maintain scoped memory, use governed tools, pause
for people, and react to conversations or business events. Typed values, connector
and channel registries, reproducible versions, observable costs and declarative UI
metadata keep every new node/integration composable without per-feature engine or
frontend rewrites.
