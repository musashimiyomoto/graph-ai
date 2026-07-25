# AGENTS.md — Backend (Graph AI)

## Overview

Backend is a Python 3.12 service built with FastAPI, SQLAlchemy async ORM, and PostgreSQL. Workflow execution is currently synchronous (in-request); moving it off the request path is tracked in the root `ROADMAP.md`.

## Commands (run from repo root)

```bash
make back-lint
make back-format
make back-typecheck
make back-test
make back-migrate MSG="describe the change"
```

Run all backend checks after any backend change:

```bash
make back-lint && make back-format && make back-typecheck && make back-test
```

## Current structure

```text
backend/
├── main.py
├── sessions.py
├── logging_config.py
├── api/
│   ├── dependencies/
│   └── routers/
├── constants/
├── db/
│   ├── migrations/
│   ├── models/
│   └── repositories/
├── enums/
├── exceptions/
├── llm/
├── nodes/
├── schemas/
├── settings/
├── usecases/
├── utils/
└── tests/
```

## Architecture rules

- API path is layered: `router -> usecase -> repository`.
- Routers are thin: validation/binding only, business logic in usecases.
- Repositories are data-access only and do not contain orchestration logic.
- Dependencies are created in `dependencies/` and wired via `Depends(...)`.
- Domain errors inherit `BaseError` and are handled globally in `main.py`.
- Cross-package imports should go through package exports (`__init__.py`) where available.
- Keep one entity per file per layer (`node.py`, `edge.py`, `execution.py`, etc.).

## Compatibility and database reset policy

- The project is pre-user and supports only the current code and schema. Backward
  compatibility is not a requirement unless the user explicitly changes this policy.
- Do not add legacy fields, aliases, dual reads/writes, fallback branches, adapters,
  backfills, or transitional migrations for older contracts.
- When a model or API contract changes, remove the superseded shape and update all
  callers, fixtures, tests, and the baseline schema directly.
- If persisted local development or test data conflicts with the current schema,
  delete the affected rows or recreate the local/test database, then rerun migrations
  and tests. Do not preserve disposable data with compatibility code.
- Never apply this reset policy to production or external data stores without an
  explicit user request.

## Execution pipeline rules

- Execution creation is initiated via `ExecutionUsecase.create_execution`.
- Runtime node handlers live in `nodes/` and implement `NodeHandler.execute(...)`.
- Node handler wiring is centralized in `nodes/registry.py` via `NodeHandlerRegistry`.
- Graph validation (acyclic graph, single input/output, connectivity) stays in execution usecase.
- For node handlers with external HTTP calls (e.g. `web_search`), API tests must mock outbound requests.

## Code style rules

- Strict typing on all functions and methods.
- Module/class/function docstrings are mandatory (Google style).
- SQLAlchemy models use `Mapped[...]` and `mapped_column(...)`.
- FastAPI parameters use `typing.Annotated` where needed.
- Imports order: stdlib -> third-party -> local.
- Keep style compatible with Ruff config (`select = ["ALL"]` with configured ignores).

## Testing rules

- Framework: `pytest` + `pytest-asyncio`.
- DB tests use testcontainers PostgreSQL (`tests/conftest.py`).
- API tests live in `tests/test_api/` and use `BaseTestCase`.
- Model factories live in `tests/factories/` and must be exported via `tests/factories/__init__.py`.
- Current coverage focuses on API and usecase behavior (execution graph validation, failure persistence, web-search node with mocked HTTP).

## Change checklist for a new backend entity

1. Add enum (if needed): `enums/{entity}.py`
2. Add model: `db/models/{entity}.py`
3. Add schemas: `schemas/{entity}.py`
4. Add repository: `db/repositories/{entity}.py`
5. Add usecase: `usecases/{entity}.py`
6. Add exceptions: `exceptions/{entity}.py`
7. Add dependency provider: `api/dependencies/{entity}.py`
8. Add router: `api/routers/{entity}.py`
9. Export public symbols in touched `__init__.py` files
10. Add factory: `tests/factories/{entity}.py`
11. Add API tests: `tests/test_api/test_{entity}.py`
12. Register router in `main.py`
13. Generate migration with `make back-migrate MSG="add {entity}"`
