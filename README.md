[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Vite 7](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![Tailwind CSS 4](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Backend CI](https://github.com/musashimiyomoto/graph-ai/actions/workflows/backend.yml/badge.svg)](https://github.com/musashimiyomoto/graph-ai/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/musashimiyomoto/graph-ai/actions/workflows/frontend.yml/badge.svg)](https://github.com/musashimiyomoto/graph-ai/actions/workflows/frontend.yml)

---

# Graph AI

Visual graph-based AI workflow builder — FastAPI + ARQ · Postgres + Redis + Qdrant + React/Vite + Ollama.

Build AI workflows as a graph: drag nodes onto a canvas, wire them together, and
run them synchronously (chat) or on a trigger (Telegram, cron schedule). Every run
is executed in the background, versioned, streamed token-by-token, and observable.

## Features

- **Visual graph editor** (React 19 + React Flow) — catalog-driven node inspector,
  undo/redo, copy-paste, multi-select, auto-layout; workflow export/import,
  duplication, and a global template library (Simple/RAG Chatbot, Telegram Echo).
- **Node types** — Input, LLM, Web Search, Template, HTTP Request, Condition
  (if/else branching), Code/Transform (sandboxed Python), Vector Ingest/Search
  (RAG), Loop (list-map & do-while), and Output.
- **Async execution engine** — ARQ + Redis background runs, per-node retries with
  backoff, wave-parallel scheduling for independent branches, a stuck-run reaper,
  per-node result persistence, SSE token streaming with a polling fallback, and
  workflow versioning with pinned reruns.
- **Multi-provider LLM** — Ollama, OpenAI, and Anthropic (the OpenAI client also
  serves any OpenAI-compatible endpoint via a custom base URL), with token
  streaming to the client.
- **RAG** — Qdrant vector store with local CPU embeddings (`fastembed`); upload
  `.pdf`/`.docx`/`.txt`/`.md` documents and search them from a workflow.
- **Channels & triggers** — chat, Telegram bots (per-user, encrypted token,
  trigger-and-reply), and cron-scheduled runs.
- **Multi-tenant hardening** — JWT auth, Fernet-encrypted secrets, per-user
  quotas (executions & tokens/day), an append-only audit log, and cost
  observability (tokens/latency per run).
- **Observability** — Prometheus metrics (`/metrics`) and optional Sentry error
  tracking across both the API and the worker.

See [ROADMAP.md](./ROADMAP.md) for what's built and what's planned next.

## Requirements

- Python 3.12
- Node.js 24
- Docker & Docker Compose

## Quick Start (Docker)

```bash
make run
```

This copies `.env.example` → `.env` and runs `docker compose up --build`.

| Service          | URL                                |
| ---------------- | ---------------------------------- |
| Frontend         | http://localhost:3000              |
| Backend (Swagger)| http://localhost:5000/docs         |
| Metrics          | http://localhost:5000/metrics      |
| ARQ dashboard    | http://localhost:8000              |
| Qdrant dashboard | http://localhost:6333/dashboard    |
| Ollama           | http://localhost:11434             |

Postgres (`5432`) and Redis (`6379`) are also exposed for local tooling.

## Local Development

```bash
make setup
```

### Backend

```bash
make back-lint              # Lint (ruff --fix)
make back-format            # Format (ruff format)
make back-typecheck         # Type check (ty)
make back-test              # Tests (pytest + testcontainers)
make back-migrate MSG="…"   # Generate Alembic migration
```

### Frontend

```bash
make front-lint             # Lint (eslint)
make front-typecheck        # Type check (tsc)
make front-test             # Tests (vitest)
make front-build            # Production build (vite)
```
