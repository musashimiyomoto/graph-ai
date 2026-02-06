SHELL := /bin/bash

.PHONY: check format typecheck test migrate run

check:
	uv run ruff check --force-exclude --fix --exit-non-zero-on-fix

format:
	uv run ruff format --force-exclude --exit-non-zero-on-format

typecheck:
	cd backend && uv run ty check .

test:
	cd backend && uv run pytest tests/

migrate:
	@set -euo pipefail; \
	backup=$$(mktemp /tmp/env.bak.XXXXXX); \
	if [ -f .env ]; then cp .env $$backup; fi; \
	cp .env.example .env; \
	sed -i 's/^POSTGRES_HOST=.*/POSTGRES_HOST=localhost/' .env; \
	trap 'if [ -f $$backup ]; then cp $$backup .env; rm -f $$backup; fi' EXIT; \
	cd ./backend && alembic revision --autogenerate -m "$${MSG:-autogen}"

run:
	cp .env.example .env && docker compose up --build
