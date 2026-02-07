# AGENTS.md — Graph AI

## Overview

Graph AI — monorepo with a layered Python backend (FastAPI + SQLAlchemy + PostgreSQL).
Frontend will be added later.

## Project layout

```
backend/          # Python 3.12 FastAPI backend
# frontend/      # TBD
```

## General rules

- Never commit secrets or `.env` files.
- Use `uv` as the Python package manager.
- Docker Compose orchestrates all services (Postgres, Redis, Chroma, Prefect).

---

# Backend

## Commands

```bash
# All commands run from the repo root

# Lint (ruff check with autofix)
make check

# Format
make format

# Type check (ty)
make typecheck

# Tests (pytest with testcontainers, requires Docker)
make test

# Run all checks
make check && make format && make typecheck && make test

# Generate Alembic migration
make migrate MSG="describe the change"

# Start the app (docker compose)
make run
```

`uv` is the package manager (`backend/pyproject.toml`).

## Structure

```
backend/
├── main.py              # FastAPI app, router registration, global error handler
├── sessions.py          # SQLAlchemy async engine & sessionmaker
├── models/              # SQLAlchemy ORM models (inherit BaseWithID / BaseWithDate)
├── schemas/             # Pydantic v2 request/response schemas
├── repositories/        # Data access layer (inherit BaseRepository[Model])
├── usecases/            # Business logic layer
├── routers/             # FastAPI routers (thin — delegate to usecases)
├── dependencies/        # FastAPI Depends() providers
├── exceptions/          # Domain exceptions (inherit BaseError with HTTP status)
├── enums/               # Python enums for domain constants
├── settings/            # pydantic-settings config classes
├── utils/               # Shared utilities (crypto, redis, etc.)
├── migrations/          # Alembic migrations
└── tests/
    ├── conftest.py      # Session-scoped Postgres testcontainer, fixtures
    ├── factories/       # factory-boy factories (AsyncSQLAlchemyModelFactory)
    └── test_api/        # API integration tests
        └── base.py      # BaseTestCase with helper assertions
```

Each domain entity (edge, node, workflow, user, etc.) follows the same pattern:
**model → schema → repository → usecase → dependency → router → test + factory**.

## Architecture rules

- **Layered architecture**: router → usecase → repository. Routers are thin — no business logic. Usecases orchestrate repositories.
- **Every package has `__init__.py`** that re-exports public symbols with `__all__`.
- **One file per entity per layer**. Example: `models/edge.py`, `schemas/edge.py`, `repositories/edge.py`, etc.
- **Dependency injection** via FastAPI `Depends()`. Providers live in `dependencies/`.
- **Exceptions** inherit `BaseError(message, status_code)` and are caught by the global handler in `main.py`.

## Code style

- **Python 3.12**, strict typing everywhere. All functions have return type annotations.
- **Ruff** with `select = ["ALL"]` — every rule enabled (except `D203`, `D213`, `COM812`).
- **Docstrings are mandatory** on every module, class, and function (Google style with `Args:`, `Returns:`, `Raises:` sections).
- Module-level docstrings are short one-liners: `"""Edge model."""`
- Class docstrings are short one-liners: `"""Directed edge between workflow nodes."""`
- Use `Mapped[type]` + `mapped_column()` for SQLAlchemy columns (never legacy `Column()`).
- Pydantic schemas use `Field(default=..., description="...", gt=0)` with explicit params.
- Response schemas use `model_config = ConfigDict(from_attributes=True)`.
- Use `typing.Annotated` for FastAPI parameter declarations.
- Named arguments everywhere: `Depends(dependency=...)`, `Field(default=...)`, `Query(gt=0)`, etc.
- No bare `assert` in tests — use `pytest.fail()` with descriptive messages.
- Imports: stdlib → third-party → local, separated by blank lines. Use package-level imports from `__init__.py` (e.g., `from models import Edge`, not `from models.edge import Edge`) except within the same package.

## Testing conventions

- **Framework**: pytest + pytest-asyncio (`asyncio_mode = "auto"`).
- **Database**: testcontainers PostgreSQL (session-scoped container, function-scoped engine/session).
- **HTTP client**: httpx `AsyncClient` with `ASGITransport` (no real server).
- **Factories**: factory-boy with custom `AsyncSQLAlchemyModelFactory.create_async(session=..., **overrides)`.
- **Test structure**: one `Test{Entity}{Action}(BaseTestCase)` class per endpoint.
  - Class attribute `url = "/edges"`.
  - Methods: `async def test_ok(self) -> None`.
  - Use `self.session`, `self.client` from `BaseTestCase.setup` fixture.
  - Use `self.create_user_and_get_token()` for authenticated requests.
  - Use `self.assert_response_dict()`, `self.assert_response_list()`, `self.assert_response_ok()`, `self.assert_has_keys()`.
- **New factories** go in `tests/factories/` and must be re-exported from `tests/factories/__init__.py`.

## Adding a new entity (checklist)

1. `enums/{entity}.py` — if the entity needs enums
2. `models/{entity}.py` — SQLAlchemy model inheriting `BaseWithID` or `BaseWithDate`
3. `schemas/{entity}.py` — `{Entity}Create`, `{Entity}Update`, `{Entity}Response`
4. `repositories/{entity}.py` — `{Entity}Repository(BaseRepository[{Entity}])`
5. `usecases/{entity}.py` — `{Entity}Usecase` with business logic
6. `exceptions/{entity}.py` — domain exceptions inheriting `BaseError`
7. `dependencies/{entity}.py` — `get_{entity}_usecase()` provider
8. `routers/{entity}.py` — FastAPI router with CRUD endpoints
9. `tests/factories/{entity}.py` — factory-boy factory
10. `tests/test_api/test_{entity}.py` — integration tests
11. Register router in `main.py`: `app.include_router(router={entity}.router)`
12. Re-export from every `__init__.py` touched
13. Generate migration: `make migrate MSG="add {entity}"`

## Verification

After ANY code change, run:

```bash
make check && make format && make typecheck && make test
```

All four must pass before considering work complete.

---

# Frontend

> TBD — frontend not yet implemented. Fill in this section when the frontend stack is chosen.
