# docs/FRONTEND.md

> **Last updated after:** Next 16.1.6 + React 19.2 migration (Feb 2026)

This file is the source of truth for frontend coding patterns.
AI agents and contributors must follow it when touching `apps/web/`.

---

## Current stack

| Package | Version | Notes |
|---|---|---|
| next | 16.1.6 | App Router only, Active LTS |
| react / react-dom | 19.2.4 | |
| typescript | 5.6.3 | |
| eslint | 9.x | Flat config (`eslint.config.mjs`) |
| eslint-config-next | 16.1.6 | Provides core-web-vitals + typescript presets |
| vitest | 4.0.18 | Unit/component tests (vite 7.x, esbuild 0.27.x) |

Node requirement: **>= 20.9.0** (current: 23.x).

---

## Commands

Run from `apps/web/`:

| Command | What it does |
|---|---|
| `npm run dev` | Start dev server |
| `npm run build` | Production build |
| `npm run test` | Run vitest |
| `npm run lint` | ESLint via `eslint .` (NOT `next lint`) |
| `npm run typecheck` | `next typegen && tsc --noEmit` |

---

## Approved patterns (use these)

### Routing & data fetching
- **App Router** (`app/` directory) — all pages are `page.tsx` files.
- **Server Components** are the default. Add `"use client"` only when the component needs browser APIs, hooks, or event handlers.
- **`fetch()` in Server Components** or **Server Actions** for data mutations.
- **`useRouter` from `next/navigation`** (not `next/router`).
- **`useSearchParams`, `usePathname`** from `next/navigation`.

### React 19
- **`ref` is a regular prop** — pass it directly, no wrapper needed.
- **`use(promise)`** — unwrap promises/context in render.
- **`useFormStatus`, `useFormState`** — for form UX patterns.
- **`useOptimistic`** — for optimistic UI updates.
- **`<form action={serverAction}>`** — server actions as form actions.

### Linting
- ESLint flat config in `eslint.config.mjs`.
- Run `eslint .` (the `lint` script), never `next lint`.

### Typecheck
- `next typegen` generates route types without a full build.
- The `typecheck` script runs `next typegen && tsc --noEmit`.

---

## Anti-patterns (do NOT use)

### Removed in Next 15+ / React 19

| ❌ Don't use | ✅ Use instead | Why |
|---|---|---|
| `getServerSideProps` | Server Components + `fetch()` | Pages Router API, removed in App Router |
| `getStaticProps` / `getStaticPaths` | `generateStaticParams` + Server Components | Pages Router API |
| `useRouter` from `next/router` | `useRouter` from `next/navigation` | `next/router` is Pages Router only |
| `React.forwardRef()` | Pass `ref` as a regular prop | Unnecessary in React 19 |
| `React.createContext` + `useContext` | `use(Context)` | `use()` is the React 19 way |
| `next lint` CLI | `eslint .` | `next lint` removed in Next 16 |
| `jsx: "preserve"` in tsconfig | `jsx: "react-jsx"` | Auto-set by Next 16 |
| Pages Router (`pages/` directory) | App Router (`app/` directory) | This repo is App Router only |

### Patterns to avoid

| ❌ Avoid | Why |
|---|---|
| `useEffect` for data fetching | Use Server Components or React Query instead |
| Large `"use client"` boundary files | Keep client components small; push logic to server components |
| `React.memo` / `useMemo` without measurement | React 19 compiler handles most cases; profile first |
| Importing from `react-dom/server` in client code | SSR APIs are server-only |

---

## Config files

| File | Purpose |
|---|---|
| `next.config.mjs` | Rewrites (`/api/:path*` → backend), `experimental.proxyTimeout` |
| `eslint.config.mjs` | ESLint flat config (core-web-vitals + typescript presets) |
| `tsconfig.json` | TypeScript config (auto-managed by Next for `jsx`, `include`) |
| `vitest.config.ts` | Test runner config |
| `.env.local` | `BACKEND_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL` |

---

## Known lint warnings (tracked, not blocking)

`eslint-plugin-react-hooks@7` introduced stricter rules. These are downgraded
to `"warn"` in `eslint.config.mjs` to avoid blocking development:

- `react-hooks/set-state-in-effect` — calling setState in useEffect callbacks
- `react-hooks/refs` — ref usage patterns
- `react-hooks/preserve-manual-memoization` — manual memo usage
- `@typescript-eslint/no-unused-vars` — stricter unused-var detection

Fix these incrementally. Do not suppress them with `eslint-disable` comments.

---

## Audit status

**0 vulnerabilities** as of the vitest 4.x upgrade (Feb 2026).
All esbuild/vite/vitest chain advisories are cleared.
