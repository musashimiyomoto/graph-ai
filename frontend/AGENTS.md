# AGENTS.md — Frontend (Graph AI)

## Overview

Frontend is a React 19 + Vite 7 + TypeScript application with Tailwind CSS 4 and React Flow UI for workflow graph editing.

## Commands (run from repo root)

```bash
make front-lint
make front-typecheck
make front-build
```

Run all frontend checks after any frontend change:

```bash
make front-lint && make front-typecheck && make front-build
```

## Current structure

```text
frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── components/
│   ├── hooks/
│   └── lib/
├── public/
├── vite.config.ts
├── eslint.config.js
└── tsconfig*.json
```

## Architecture rules

- `App.tsx` is the orchestration layer that composes major hooks and UI blocks.
- Reusable logic belongs in hooks (`src/hooks/*`), not in visual components.
- API communication is centralized in `src/lib/api.ts`.
- Shared API/domain types are defined in `src/lib/types.ts`.
- Keep components focused and single-purpose (`one component per file`).

## API and runtime rules

- API base path is `/api` in frontend code.
- Dev proxy is defined in `vite.config.ts` and currently targets `http://backend:5000` with `/api` prefix rewrite.
- Auth token lifecycle is managed through `setToken(...)` in `src/lib/api.ts` and auth hooks.
- When backend contracts change, update `src/lib/types.ts`, `src/lib/api.ts`, and affected hooks/components together.

## Code style rules

- Functional components only.
- Use strict TypeScript; no `any`, no `@ts-ignore`.
- Prefer named exports for components and utilities.
- Tailwind utility classes are the default styling approach.
- File naming:
  - Components: `PascalCase.tsx`
  - Hooks/utilities: `camelCase.ts`
- Imports order: React -> third-party -> local.

## Validation checklist after changes

1. Lint passes: `make front-lint`
2. Typecheck passes: `make front-typecheck`
3. Production build passes: `make front-build`
4. If API was touched, manually verify core flows:
   - auth login/register
   - workflow create/select/delete
   - node/edge editing
   - execution run and history
