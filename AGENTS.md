# AGENTS.md — Graph AI Monorepo

This root file contains only shared rules.

Domain-specific rules are split:

- Backend: `backend/AGENTS.md`
- Frontend: `frontend/AGENTS.md`

For full-stack tasks, follow both files.

## Shared rules

- Never commit secrets or `.env` files.
- Use `uv` for Python dependency management.
- Use `npm` for frontend dependency management.
- Use `docker compose` from the repo root for local orchestration.

## Shared commands (from repo root)

```bash
make setup
make run
```
