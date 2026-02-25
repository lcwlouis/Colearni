# apps/web

Minimal Next.js scaffold for Colearni frontend contracts.

## Setup

Copy `apps/web/.env.example` to `apps/web/.env.local`.

- `BACKEND_BASE_URL`: target backend for Next `/api/*` rewrite.
- `NEXT_PUBLIC_API_BASE_URL`: keep `/api` in local dev to avoid CORS.

## Commands

Run in `apps/web`: `npm install`, `npm run dev`, `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build`.

PR19 uses same-origin proxying for browser API access; direct backend-origin CORS is deferred to PR22.
