# Graph AI — Roadmap

Visual graph-based AI workflow builder (FastAPI + React + PostgreSQL).
This document tracks where the product is today and the sequenced plan to grow it
into an async, multi-provider orchestration platform.

## Where we are today

- **Backend** — layered `router → usecase → repository`, 6 entities (User, Workflow,
  Node, Edge, Execution, LLMProvider), JWT auth, ~34 API tests on testcontainers.
- **Frontend** — React 19 + React Flow graph editor, catalog-driven node inspector,
  4 node types, pixel-art theme.
- **Execution engine** (`backend/usecases/execution.py`) — 4 node types
  (`INPUT`, `LLM`, `WEB_SEARCH`, `OUTPUT`), correct graph validation
  (single input/output, acyclic via Kahn, connectivity via DFS).

## Key limitations driving priorities

1. Execution is **fully synchronous, inside the HTTP request** — no queue/worker;
   the client never observes `RUNNING`; long LLM calls block the worker.
2. **Ollama only** — no cloud providers.
3. **No secret storage** — `utils/crypto.py` is bcrypt-for-passwords only; the
   provider has no `api_key` field, and `config` (JSONB) is returned to the client.
4. **Intermediate node outputs are not persisted** — only the final output is stored;
   on mid-graph failure only a free-text `error` survives.
5. **No retries / backoff / stuck-execution reaper** — a non-domain exception can
   strand an execution in `RUNNING` forever.
6. **No observability** — no logging, metrics, error tracking, or rate limiting.
7. **Data is strictly `str`, format only `txt`** — no typed ports, files, or multimodality.
8. **No frontend tests**; plain `useState` state, no undo/redo, copy-paste, or auto-layout.
9. **No streaming** — Ollama is called with `stream: False`.

---

## Phase 0 — Hygiene & foundation ✅ done

Cheap changes that de-risk everything else.

- [x] Fail-fast when the default JWT secret is used in production (`settings/auth.py`,
      gated by `ENVIRONMENT`).
- [x] Catch non-`BaseError` in `create_execution`, roll back, and mark `FAILED` so an
      execution can no longer strand in `RUNNING` (`usecases/execution.py`).
- [x] Structured logging with execution-id context (`logging_config.py`, wired in `main.py`).
- [x] Refresh `backend/AGENTS.md` (removed Prefect, `flows/`, `integrations/`, `models/`).
- [x] Run Alembic migrations in CI: `alembic upgrade head` + `alembic check` catches
      model↔migration drift (`.github/workflows/backend.yml`).
- [x] LLM node happy-path test with mocked Ollama chat (`tests/test_api/test_execution.py`).

## Phase 1 — Asynchronous execution ✅ done

Unblocks streaming, long pipelines, and scale.

- [x] Move execution off the request path with **ARQ + Redis** (chosen via a real-Redis
      PoC test). `POST /executions` validates the graph, persists `CREATED`, enqueues, and
      returns `202` immediately; a worker (`worker.py`) runs it with its own session.
      Wiring: `settings/redis.py`, `main.py` lifespan pool, `api/dependencies/queue.py`,
      `docker-compose.yml` `redis`+`worker` services.
- [x] Per-node result table (`node_executions`: status, output, timings, error) with
      per-node persistence in the runner and a `GET /executions/{id}/nodes` endpoint —
      pinpointed failures and the foundation for resumability + per-node UI status.
- [x] Per-node retries with exponential backoff (retryable errors only) and a per-node
      wall-clock timeout (`constants/retry.py`, runner in `usecases/execution.py`).
- [x] Idempotency of enqueued executions via ARQ `_job_id="execution:{id}"` (dedupes
      double-submits).
- [x] Reaper for executions stuck in `RUNNING` (worker crash mid-run) — ARQ cron
      `reap_stuck_executions` + `ExecutionUsecase.reap_stuck_executions`.
- [x] Parallelize independent branches via wave scheduling — each concurrent node runs on
      its own session (`_run_nodes_parallel` in `usecases/execution.py`); the worker enables
      it by passing `session_factory`.
- [x] Frontend consumes a `GET /executions/{id}/stream` SSE endpoint (fetch + `ReadableStream`
      with the Bearer header) instead of interval polling (`api.streamExecution`,
      `useExecutions.ts`). Server-side status stream today; upgrading to Redis pub/sub for
      true push is a Phase 5 refinement.

## Phase 2 — Multi-provider LLM + secrets (2–4 weeks)

- [x] Real key encryption: Fernet (`utils/encryption.py`, `settings/encryption.py` with prod
      fail-fast) + encrypted, write-only `LLMProvider.api_key` (migration `709163b05319`);
      the key is never returned in any response. `config` stays for non-secret settings —
      secrets belong in `api_key`.
- [x] OpenAI / Anthropic / OpenAI-compatible clients (`llm/openai.py`, `llm/anthropic.py`;
      enum values `OPENAI`/`ANTHROPIC`/`OPENAI_COMPATIBLE`; `create_llm_client(provider, api_key)`
      decrypts `api_key` at construction and requires it for cloud providers). Anthropic uses the
      official `anthropic` SDK (streaming + `get_final_message`), default model `claude-opus-4-8`.
      Each client wraps SDK errors into domain `LLMProviderConnectionError` (retryable) /
      `LLMProviderConfigError` (non-retryable, e.g. bad key).
- [x] Generation params per node: `temperature`, `max_tokens`, `top_p` (`GenerationParams`
      schema, opt-in via the new `optional_number` widget so unset params are omitted — critical
      for Anthropic models that reject `temperature`). Honored by every client.
- [x] Token streaming from provider through to the UI: every client exposes `stream_chat`
      (`AsyncIterator[str]`); the LLM node forwards each delta via a `NodeExecutionContext.on_token`
      sink; the worker publishes deltas to the Redis channel `execution:{id}:tokens`
      (`streaming/tokens.py`); `GET /executions/{id}/stream` multiplexes `token` + `status` SSE
      frames (`ExecutionUsecase.stream_execution`); the frontend accumulates deltas per node and
      renders them live (`useExecutions.liveTokens`, `LiveOutput.tsx`). Token streaming is
      best-effort — a pub/sub failure never breaks the authoritative status stream.

## Phase 3 — Richer graph & node types (4–6 weeks)

- [x] Typed ports (`PortType` = text / json / file / list) on `NodeGraphSpec`
      (`input_port`/`output_port`); edge type-compat validated at two layers —
      `EdgeUsecase.create_edge` (→ `EdgePortMismatchError`, HTTP 400) and
      `ExecutionUsecase._build_graph_context` (defense in depth). Compatibility is the single
      `ports_compatible` choke point (exact-match today; ready for a coercion table). Frontend
      guards connections client-side via `isValidConnection` in `GraphCanvas`. All current nodes
      are `text`, so this installs the machinery future non-text nodes need.
- [ ] New nodes: Prompt/Template, Condition/Router, Code/Transform, HTTP Request, RAG/Vector search, Loop/Map.
- [x] Plugin-based node registration: a single `NodeDefinition` (in `nodes/definition.py`)
      co-locates a node's type, label, icon, ports, field specs, and handler factory next to its
      handler; `nodes/registry.py` derives both the handler map and the UI catalog from one
      `NODE_DEFINITIONS` list (adding a node = one module + one list entry + its `NodeType` member).
      `nodes/catalog.py` removed.
- [ ] Workflow versioning + run a specific version (today edits mutate the live graph).

## Phase 4 — Product UX (parallel, 3–5 weeks)

- [ ] Undo/redo, copy-paste, multi-select, auto-layout in the editor.
- [ ] Execution panel: active/failed node highlighting, per-node inline output, live log.
- [ ] React Query in place of hand-rolled `useState`/`useEffect` (cache, invalidation, optimistic updates).
- [ ] Workflow template library, JSON export/import, duplication.
- [ ] Frontend tests (Vitest + Testing Library) — currently zero.

## Phase 5 — Production readiness (cross-cutting)

- [ ] Auth: refresh tokens (today a single 30-min access token), login rate limiting,
      optional roles, logout/revocation.
- [ ] Observability: metrics (Prometheus), error tracking (Sentry), readiness that also
      checks Ollama/providers.
- [ ] Multi-tenant quotas, audit log, CORS middleware (absent in `main.py`).
- [ ] Cost observability — tokens/latency per execution.

---

### Quick wins this week

Default `secret_key` fail-fast · catch all exceptions in execution · logging ·
migrations in CI · LLM node test · fix `AGENTS.md`.

### North star

From a synchronous, single-user Ollama editor → an **asynchronous, multi-provider
orchestration platform** with typed data, streaming, and observability.
