SHELL := /bin/bash

.PHONY: check format migrate

check:
	ruff check .

format:
	ruff format .

migrate:
	@set -euo pipefail; \
	backup=$$(mktemp /tmp/env.bak.XXXXXX); \
	if [ -f .env ]; then cp .env $$backup; fi; \
	cp .env.example .env; \
	sed -i 's/^POSTGRES_HOST=.*/POSTGRES_HOST=localhost/' .env; \
	trap 'if [ -f $$backup ]; then cp $$backup .env; rm -f $$backup; fi' EXIT; \
	alembic revision --autogenerate -m "$${MSG:-autogen}"
