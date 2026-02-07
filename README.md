[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/badge/ty-checked-blue.svg)](https://github.com/astral-sh/ty)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Vite 7](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![Tailwind CSS 4](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Backend CI](https://github.com/iosifkrokai/graph-ai/actions/workflows/backend.yml/badge.svg)](https://github.com/iosifkrokai/graph-ai/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/iosifkrokai/graph-ai/actions/workflows/frontend.yml/badge.svg)](https://github.com/iosifkrokai/graph-ai/actions/workflows/frontend.yml)

---

# Graph AI

Visual graph-based AI workflow builder — FastAPI + React + PostgreSQL.

## Requirements

- Python 3.12 & [uv](https://github.com/astral-sh/uv)
- Node.js 24
- Docker & Docker Compose

## Quick Start

```bash
cp .env.example .env
make run
```

| Service     | URL                    |
| ----------- | ---------------------- |
| Frontend    | http://localhost:3000   |
| Swagger     | http://localhost:5000/docs |
| Prefect     | http://localhost:4200   |

## Development

```bash
# Backend
make back-check        # Lint (ruff)
make back-format       # Format (ruff)
make back-typecheck    # Type check (ty)
make back-test         # Tests (pytest + testcontainers)
make back-migrate MSG="description"

# Frontend
make front-lint        # ESLint
make front-typecheck   # TypeScript
make front-build       # Production build
```

## Tech Stack

**Backend** — FastAPI · SQLAlchemy · PostgreSQL · Redis · ChromaDB · Prefect · Ollama

**Frontend** — React 19 · Vite 7 · TypeScript · Tailwind CSS 4 · React Flow
