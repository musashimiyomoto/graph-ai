# Deepening Roadmap — graph-ai

A companion to `ROADMAP.md`. Where the roadmap adds **breadth** (new phases, node types,
features), this document is about **depth**: making what already exists correct, robust,
secure, and genuinely usable. Every item below hardens or polishes existing code — none
introduce new capabilities.

Severity reflects impact on a real user of a *current* feature. File references are current
as of this writing.

Legend: **[H]** high · **[M]** medium · **[L]** low.

---

## Top priorities (do these first)

1. ~~**SSRF guard on all outbound URLs**~~ ✅ done — `utils/network.py::blocked_url_reason` with
   two modes: strict (HTTP node blocks loopback/private/link-local/…) and lenient (providers block
   link-local/metadata/reserved/multicast but allow private/loopback so self-hosted Ollama works).
   Wired into the HTTP node, provider create/update, `get_models`, and the LLM node.
2. ~~**FK indexes**~~ ✅ done — `index=True` on all FK columns + migration `d3e5a7c1f9b2`
   creating 9 indexes (`workflows.owner_id`, `nodes.workflow_id`, `edges.*`, `executions.workflow_id`,
   `node_executions.*`, `llm_providers.user_id`).
3. ~~**Deterministic multi-parent ordering**~~ ✅ done — `_build_graph_context` now processes
   nodes in stable id order and sorts inbound/outbound adjacency, so fan-in `parent_values` (and
   topological/wave order) are reproducible regardless of DB edge-return order.
4. ~~**Reaper/worker race + `started_at` semantics**~~ ✅ done — `started_at` is now set on the
   CREATED→RUNNING claim (age measures runtime, not queue wait); terminal writes and the claim use
   an atomic compare-and-set (`ExecutionRepository.update_status_if`) so the reaper and worker can't
   clobber each other or double-run.
5. ~~**Shared client-side field validation**~~ ✅ done — `lib/validation.ts::validateFields`
   (required + `min_length` + `ge`/`le` + `select`) used by `CreateNodeDialog` and `InspectorPanel`
   (inline per-field errors; the inspector won't autosave invalid config); `NumberInput` clamps on blur.
6. ~~**Inspector autosave: flush-on-switch + retry-on-failure**~~ ✅ done — flushes the outgoing
   node's pending valid edits on switch (no more loss inside the debounce window); advances the
   saved snapshot only after a confirmed success (`onSaveNode` now returns `Promise<boolean>`);
   shows a saving…/saved ✓/retry indicator.
7. ~~**Pagination + ordering on list endpoints**~~ ✅ done — `get_all` now orders deterministically
   by primary key (optional `descending`) and supports `limit`/`offset`; the growing lists
   (`GET /executions`, `/executions/{id}/nodes`) take `limit`/`offset` query params via a shared
   `Pagination` dependency (default 50, max 100), executions returned newest-first. Bounded lists
   (nodes/edges) get deterministic order without truncation.
8. **Auth rate limiting** + **secure-by-default keys** (remove committed Fernet key) (`[H]`, security).
9. **Workflow delete confirmation** — one misclick destroys a whole flow (`[H]`, frontend).
10. **SSE 5-minute cap** — streams close mid-run for any execution > 5 min (`[M]`, engine+API).

---

## 1. Security hardening

- ~~**[H] SSRF on user-controlled outbound requests.**~~ ✅ **Done.** Shared guard
  `utils/network.py::blocked_url_reason(url, *, allow_private)` resolves the host and blocks
  disallowed ranges. Strict mode (HTTP node) blocks loopback/private/link-local/reserved/
  multicast/unspecified; lenient mode (providers — Ollama etc. are legitimately private) blocks
  only link-local (incl. `169.254.169.254` metadata)/reserved/multicast/unspecified. Wired into
  `nodes/http_request.py` (strict), `usecases/llm_provider.py` create/update/`get_models`, and
  `nodes/llm.py` (lenient). Unresolvable hosts are allowed (nothing to connect to). Covered by
  `tests/test_network.py` + an HTTP-node loopback test.
- **[H] No rate limiting / lockout anywhere.** `POST /auth/login` + `/auth/register`
  (`api/routers/auth.py:14-31`), no limiter middleware. Enables password guessing and a
  bcrypt-CPU-DoS. **Fix:** IP+account rate limiting (Redis token bucket — Redis is already a dep).
- **[H] Weak keys used silently unless `ENVIRONMENT == "production"` exactly.** JWT default
  `secret_key="secret"` and a **committed Fernet key** (`settings/auth.py:23`,
  `settings/encryption.py:25-28`); guards fire only on the exact string `production`
  (`settings/auth.py:42-45`). A deploy that forgets the env var signs tokens with a guessable
  key and encrypts API keys with a public key. **Fix:** secure-by-default — refuse to boot with
  default keys unless `ENVIRONMENT in {local,test}`; remove the hard-coded Fernet key from source.
- **[M] No CORS middleware** (`main.py:45-70`). The shipped SPA can't call the API cross-origin,
  and the common late "fix" is `allow_origins=["*"]`. **Fix:** explicit allowlist from settings.
- **[M] Password has no length bounds** (`schemas/user.py:17`). bcrypt silently truncates past
  72 bytes → distinct long passwords collide; no minimum strength. **Fix:** `min_length=8,
  max_length=72` on `UserCreate.password` (and bound `LoginCreate.password`).
- **[M] Register leaks account existence** (`usecases/auth.py:210-211`, 409 on duplicate).
  Login is safely generic; registration enables enumeration. **Fix:** neutral response +/or rate limit.
- **[M] Single 30-min token: no refresh/revocation, no `jti`/`iat`** (`usecases/auth.py:29-55`).
  A leaked token is valid for its full life; no logout. **Fix:** add `iat`+`jti` now
  (cheap, forward-compatible), then a refresh token + Redis revocation list.
- **[L]** No `aud`/`iss` on JWT decode (`usecases/auth.py:71-75`); Fernet single-key (no
  `MultiFernet` rotation, `utils/encryption.py:7`); token in `localStorage` with no proactive
  expiry (`frontend/.../useAuthSession.ts:6,27,71`).

## 2. Data layer

- ~~**[H] No indexes on any foreign key.**~~ ✅ **Done.** `index=True` on all FK columns +
  migration `d3e5a7c1f9b2` creating 9 indexes (`ix_workflows_owner_id`, `ix_nodes_workflow_id`,
  `ix_edges_{workflow,source_node,target_node}_id`, `ix_executions_workflow_id`,
  `ix_node_executions_{execution,node}_id`, `ix_llm_providers_user_id`).
- **[M] Multi-step operations aren't atomic** — the base repo commits inside every write
  (`db/repositories/base.py:31,51,114,133,154`). `register` commits user then default provider
  separately (`usecases/auth.py:213-230`); `create_execution` commits then enqueues
  (`usecases/execution.py:139-148`). A failure between steps leaves partial state (user with no
  provider; a `CREATED` execution that never runs and is **never reaped** — the reaper only
  looks at `RUNNING`, `usecases/execution.py:255-256`). **Fix:** flush-not-commit repos + one
  commit per usecase (unit of work); have the reaper also consider stale `CREATED`.
- **[M] Timezone-less datetime columns** (`db/models/base.py:37-45`, `execution.py:37-41`)
  compared against Python-side naive UTC in the reaper (`usecases/execution.py:252`). Correctness
  depends on the DB session TZ being UTC. **Fix:** `DateTime(timezone=True)` + tz-aware compares.
- **[M] Missing unique constraints** — none on `edges(workflow_id, source, target)` or
  `llm_providers(user_id, name)`. Duplicate edges and provider names are silently allowed.
  **Fix:** composite unique constraints + migration + clean 409.
- **[L]** `delete_all` is N+1 (`db/repositories/base.py:140-156`); `delete_by`/`update_by`
  read-then-write. Use bulk statements as data grows.

## 3. Execution engine

- ~~**[H] Nondeterministic multi-parent merge order.**~~ ✅ **Done.** `_build_graph_context`
  builds the node maps from `sorted(nodes, key=id)` and sorts each `inbound`/`outbound` list after
  the edge loop, so `parent_values` and traversal order no longer depend on DB edge-return order.
  Covered by `test_fan_in_merge_order_is_deterministic`.
- ~~**[H] Reaper races the worker; `started_at` measures the wrong interval.**~~ ✅ **Done.**
  `started_at` is set on the CREATED→RUNNING claim, and both the claim and the terminal writes use
  `ExecutionRepository.update_status_if` — a single `UPDATE ... WHERE id AND status = :expected`
  compare-and-set. The reaper (RUNNING→FAILED) and the worker (RUNNING→SUCCESS/FAILED) can no
  longer clobber each other, and a duplicate delivery can't double-run. Covered by
  `test_status_cas_prevents_clobber`. (Cancelling the actual ARQ job on reap is still open — the
  CAS just prevents the stale worker from clobbering the reaped state.)
- **[M] SSE status stream hard-caps at 5 minutes** (`STREAM_MAX_ITERATIONS=300 ×
  STREAM_POLL_SECONDS=1.0`, `constants/execution.py:9-10`) while a single node can legitimately
  run up to `NODE_TIMEOUT_SECONDS(300) × MAX_NODE_ATTEMPTS(3)` = 900 s. Any run > 5 min ends the
  stream with no terminal status → a spinner that never resolves. **Fix:** align the cap with
  worst-case run time, or emit an explicit "stream expired, resume polling" frame instead of a
  silent `None`. (Pairs with the frontend polling-fallback item.)
- **[M] Streaming pins a pooled DB connection for the stream lifetime.** The request-scoped
  session is held through `_pump_status` (`api/routers/execution.py:82-107`,
  `usecases/execution.py:471-500`); with `pool_size=10,max_overflow=20` ~30 concurrent viewers
  exhaust the pool and block the whole API. **Fix:** open/close a short-lived session per poll.
- **[M] BaseError failure path doesn't roll back the session** before `_mark_execution_failed`
  (`usecases/execution.py:211-215` vs the generic branch at 218). In serial mode a poisoned
  transaction makes the FAILED-status commit itself throw. **Fix:** `await session.rollback()` in
  the BaseError branch too.
- **[M] Parallel partial-failure surfaces an arbitrary error and writes no "skipped" rows.**
  `_run_nodes_parallel` raises the first exception in `ready` order, discarding siblings; unreached
  nodes get no `node_execution` row (`usecases/execution.py:622-652`). **Fix:** aggregate wave
  errors; write `SKIPPED`/not-run rows so the UI can distinguish failed from never-reached.
- **[M] No global node-output size cap.** Only the HTTP node truncates; LLM/web_search/template/
  output are unbounded into `Text`/JSONB (`db/models/node_execution.py:33`). A runaway LLM
  response bloats memory and DB. **Fix:** global max-output-chars + truncation marker in
  `_record_node_result`.
- **[M] Stuck timeout can be shorter than a legitimate run** (`STUCK_EXECUTION_TIMEOUT_SECONDS
  =3600` vs up to 900 s/node × N serial + backoff). **Fix:** heartbeat/last-progress based
  detection, not absolute start age.
- **[L]** Retries are invisible and inflate reported duration (`usecases/execution.py:705-747`);
  confirm the dead "non-input node with no parents" branch (`:773-775`) vs connectivity validation.

## 4. API & schemas

- **[H] No pagination or ordering on any list endpoint** (`db/repositories/base.py:57-76`;
  all `list_*` routes). Executions and node_executions grow unboundedly → ever-larger payloads
  (slow DoS) and non-deterministic UI order. **Fix:** `limit`/`offset` (or keyset) with a hard cap
  + `ORDER BY id DESC`.
- **[M] No length/size bounds on user strings/payloads** — `WorkflowCreate.name`,
  `ExecutionInputPayload.value`, `LLMProviderCreate.name/config`, `UserCreate.password` are all
  unbounded, and there's no request-size middleware. Multi-MB `input_data.value` lands in JSONB
  and LLM prompts. **Fix:** `max_length` aligned with DB widths + bound the execution input;
  consider a body-size limit.
- **[M] Readiness probe is always 200 and ignores Redis** (`api/routers/health.py:21-32`,
  `usecases/health.py:35`). Returns ready even when Postgres is down and never checks Redis,
  though executions can't enqueue without it. **Fix:** 503 when any dependency is unhealthy; add a
  Redis/ARQ ping.
- **[L/M] Free-form `config`/`dict` fields** echoed back verbatim (`LLMProviderCreate.config`,
  `schemas/llm_provider.py:49,61,85`). **Fix:** a typed `config` model per provider or at least a
  size/key bound. (Node `data` is fine — it's catalog-validated.)
- **[L]** No generic `Exception` handler / request-context logging at the app boundary
  (`main.py:48-60`); `async_engine` never `dispose()`d on shutdown (`main.py:38-42`); dead
  `if not user` branch in `login` (`usecases/auth.py:179-180`).

## 5. Node handlers (usability depth)

- **[H] "Web Search" isn't a web search.** It hits the DuckDuckGo *Instant Answer* API and reads
  only `AbstractText`/`RelatedTopics` (`nodes/web_search.py:23,92-114`), which is populated only
  for encyclopedic entities. Real queries return "No search results found" downstream. **Fix:**
  use the HTML/lite results endpoint (parse title/snippet/URL) or make the provider configurable;
  at minimum distinguish "no abstract" from "no results" and document the limitation.
- **[M] HTTP node: unencoded URL substitution + silent truncation.** `{{input}}` is spliced into
  the URL without percent-encoding (`nodes/http_request.py:59`), so the documented `?q={{input}}`
  breaks for any text with spaces/`&`/`#`. Response is silently cut at 10k with no marker
  (`:21,50`), returned as `.text` regardless of content-type, and headers can't be templated.
  **Fix:** URL-encode on substitution; configurable cap + truncation marker; allow `{{input}}` in
  headers. (SSRF is covered in §1.)
- **[M] Template node: single exact-match `{{input}}`, silent whole-payload loss.**
  `render_input` (`nodes/rendering.py:23-34`) does a literal replace; `{{ input }}` or `{{INPUT}}`
  substitutes nothing and drops the entire upstream text with no error, and you can't reference an
  individual parent. **Fix:** tolerate whitespace, support indexed placeholders (`{{input.0}}`),
  warn on an unresolved placeholder / a parented template with no placeholder.
- **[M] Output node ignores its `format` field and merges nondeterministically**
  (`nodes/output.py:19`; `format` at `:49-55` is dead). **Fix:** deterministic ordering (see §3)
  + optional separator/template instead of a hardcoded newline join.
- **[M] LLM node: streaming retries duplicate tokens** to the client (partial attempt + full
  retry concatenated, `nodes/llm.py:122-129`); **no input-size guard** (`:115`) so an oversized
  upstream fails the run opaquely. **Fix:** emit a per-node "attempt reset" marker on retry (or
  publish only on success); optional max-input-chars with a clear pre-flight error.
- **[L]** `system_prompt` is `required=True` but accepts `""` (`nodes/llm.py:181-190`); web_search
  query has no length cap and the abstract counts against `max_results`; `input` node `format` is a
  no-op widget; `PortType` advertises `JSON/FILE/LIST` that no node uses.

## 6. Node config validation (save-time)

- **[M] Untyped fields skip validation entirely.** `_validate_node_field` only checks present
  validators (`usecases/node.py:49-92`); fields with `validators={}` (LLM `system_prompt`, HTTP
  `headers`/`body`) get no type check and persist any JSON, failing only at run time. **Fix:** a
  declared `type` on `NodeFieldSpec`, validated for every field.
- **[L]** `bool` passes numeric `ge/le` (int subclass); optional numeric params can't be unset via
  PATCH (`exclude_none` strips explicit null, `usecases/node.py:337,347`); no max-length caps and
  no cross-field/semantic checks (e.g. model belongs to provider).

## 7. Frontend — field validation & inspector

- **[H] Client enforces only `required`, ignoring every value validator.** `NumberInput` passes
  raw input through with no clamp (`NumberInput.tsx:45`; clamp only runs from the ▲/▼ buttons);
  `CreateNodeDialog` validation checks only `required` (`CreateNodeDialog.tsx:206-235`);
  `InspectorPanel` validates nothing. So `temperature=999`, a 1-char required prompt, or an
  out-of-range value save locally and fail server-side with an opaque banner. **Fix:** a shared
  `validateFields(fields, data)` covering `required`+`min_length`+`ge`/`le`+`select`, used in both
  the dialog and the inspector; clamp `NumberInput` on change; inline per-field messages.
- **[H] Inspector autosave loses edits and swallows failures.** Switching nodes within the 400 ms
  debounce clears the pending timer and overwrites `draftData` → silent edit loss
  (`InspectorPanel.tsx:206-245`); and `lastSavedSnapshotRef` is advanced *before* the await, so a
  failed PATCH is marked saved and never retried (`:239-242`). **Fix:** flush-on-switch (save the
  previous node before resetting), advance the snapshot only after success, add a "saving…/saved/
  retry" affordance; capture `node.id` at effect entry to prevent wrong-node writes.
- **[M] Clearing a required number silently becomes `0`** (`Number('')===0`,
  `InspectorPanel.tsx:72`). **[M] Stale provider/model id** (deleted provider) blanks the dropdown
  while the dead id stays saved (`:124-172`); warn on deleting a referenced provider.

## 8. Frontend — UX, streaming, safety

- **[H] Workflow delete has no confirmation** (`WorkflowSidebar.tsx:130-136`) — one misclick
  destroys the whole flow (its nodes/edges/executions). Account delete *does* confirm — make it
  consistent. **[M]** node/edge/provider delete also unconfirmed.
- **[M] Build mode never surfaces run-validity.** `runDisabledReason` (exactly one input/output,
  txt format) is passed only to Chat (`App.tsx:104-128,266`); while building, the user gets no hint
  their graph is unrunnable. **Fix:** a persistent validity chip in Build + mark offending nodes.
- **[M] API layer robustness.** DELETEs call `response.json()` unconditionally — a `204` throws and
  a successful delete shows an error (`api.ts:43-50`); network errors don't match `ApiError` →
  banner shows `undefined` (`api.ts:41`, `useAuthSession.ts:39-48`); SSE `JSON.parse` is unguarded
  per frame so one bad frame kills the stream (`api.ts:197-209`). **Fix:** 204/empty-body guard,
  normalize thrown errors to `ApiError`, per-frame try/catch.
- **[M] No polling fallback when SSE is unavailable** (`useExecutions.ts:84-124`) — a running
  execution can hang on "running…" forever. **Fix:** if the stream fails and the latest execution
  is still active, poll `refreshExecutions` until it settles. (Pairs with §3 SSE cap.)
- **[M] Chat live view mismatches final output** — streams all nodes' tokens concatenated then
  snaps to just `output_data.value` (`ChatPanel.tsx:30-35,47`); smooth auto-scroll fires on every
  token and yanks the viewport (`:88-90`). **Fix:** stream only the output node's tokens;
  auto-scroll only when near bottom, `behavior:'auto'` while streaming.
- **[M] Single global error banner** — not dismissible, overwrites, no auto-hide
  (`AppShell.tsx:107`, `App.tsx:26`). **Fix:** dismissible auto-expiring toasts; scope validation
  errors to their field.
- **[L]** Modals lack focus trap/`role="dialog"`/Escape consistency (`CreateNodeDialog`,
  `ProviderManager`, `ExecutionHistory`) — shared `Modal` wrapper; context menu can render
  off-screen (`NodeContextMenu.tsx:31-35`); `ACTIVE_STATUSES` duplicated
  (`useExecutions.ts:12`, `ChatPanel.tsx:7`); Inspector re-implements provider/model fetching
  instead of the shared hooks (`InspectorPanel.tsx:247-299`); AuthScreen keeps error across
  tab-switch and has no client-side password check.

## 9. Observability & ops (existing-feature depth)

- **[M]** Readiness 503 semantics + Redis check (see §4). **[L]** Generic exception handler with
  request-context logging; engine `dispose()` on shutdown; persist retry attempts / per-attempt
  timing so the UI can show "retried N times"; guard invalid dates in `ExecutionList`.

---

## Notes

- Items are cross-referenced where they share a root cause (SSE cap ↔ polling fallback;
  nondeterministic order ↔ output/format; SSRF spans provider + HTTP node).
- **Already solid — do not redo:** consistent ownership/IDOR checks across usecases; API keys
  encrypted at rest and absent from responses; login doesn't leak account existence; deep graph
  validation (cycles, single in/out, connectivity, port compat, dangling edges); SSE ownership
  checked before streaming; node `data` catalog-validated with unknown-field rejection; prod
  guards on default JWT/Fernet keys; retries+timeouts; parallel nodes on isolated sessions; pool
  `pre_ping`/`recycle`.
