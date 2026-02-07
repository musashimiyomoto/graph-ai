SHELL := /bin/bash

.PHONY: back-check back-format back-typecheck back-test back-migrate \
        front-lint front-typecheck front-build \
        run

# ── Backend ──────────────────────────────────────────────

back-check:
	uv run ruff check --force-exclude --fix --exit-non-zero-on-fix

back-format:
	uv run ruff format --force-exclude --exit-non-zero-on-format

back-typecheck:
	cd backend && uv run ty check .

back-test:
	cd backend && uv run pytest tests/

back-migrate:
	@set -euo pipefail; \
	backup=$$(mktemp /tmp/env.bak.XXXXXX); \
	if [ -f .env ]; then cp .env $$backup; fi; \
	cp .env.example .env; \
	sed -i 's/^POSTGRES_HOST=.*/POSTGRES_HOST=localhost/' .env; \
	trap 'if [ -f $$backup ]; then cp $$backup .env; rm -f $$backup; fi' EXIT; \
	cd ./backend && alembic revision --autogenerate -m "$${MSG:-autogen}"

# ── Frontend ─────────────────────────────────────────────

front-lint:
	cd frontend && npm run lint

front-typecheck:
	cd frontend && npx tsc -b

front-build:
	cd frontend && npm run build

# ── Common ───────────────────────────────────────────────

run:
	cp .env.example .env && docker compose up --build
