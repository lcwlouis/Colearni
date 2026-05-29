# Phase 16.6 Marketing Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public, workspace-free product/marketing site (Home, How it works, Pedagogy, Pricing, Contact) at `/`, with a workspace-aware redirect into the relocated `/dashboard`, an "elevated same-family" aesthetic, and light/dark theming that follows the OS.

**Architecture:** A Next.js `(marketing)` route group owns the public paths and provides its own nav/footer/themed wrapper. The current dashboard page moves from `app/page.tsx` to `app/dashboard/page.tsx` (verbatim) so `/` is free for marketing. A fake-login helper reuses the existing `ensureWorkspaceId()` localStorage flow. Marketing-only dark mode uses Tailwind v4's `prefers-color-scheme` `dark:` variant, scoped so the product UI is untouched.

**Tech Stack:** Next.js 16 App Router, React 19, Tailwind CSS v4, `next/font/google` (Geist + Fraunces), `lucide-react`, Vitest + Testing Library + jsdom.

---

## File Structure

```
apps/web/
  app/
    layout.tsx                         # MODIFY: add Fraunces font variable
    globals.css                        # MODIFY: marketing theme tokens + reveal keyframes
    dashboard/page.tsx                 # CREATE (moved from app/page.tsx)
    page.tsx                           # DELETE (moves to dashboard/)
    (marketing)/
      layout.tsx                       # CREATE: nav + footer + themed wrapper
      page.tsx                         # CREATE: Home (+ redirect gate)
      how-it-works/page.tsx            # CREATE
      pedagogy/page.tsx                # CREATE
      pricing/page.tsx                 # CREATE
      contact/page.tsx                 # CREATE
    trails/page.tsx                    # MODIFY: home link / -> /dashboard
    trails/[id]/page.tsx               # MODIFY: home links / -> /dashboard
  components/marketing/
    MarketingNav.tsx                   # CREATE: top nav + Log in button
    MarketingFooter.tsx                # CREATE
    GraphHero.tsx                      # CREATE: animated SVG concept-graph motif
    ProductPreview.tsx                 # CREATE: in-CSS faux product shot
    SectionReveal.tsx                  # CREATE: IntersectionObserver reveal wrapper
    RedirectGate.tsx                   # CREATE: workspace-aware redirect on /
    EnterAppButton.tsx                 # CREATE: shared fake-login CTA button
    marketing-content.ts               # CREATE: nav links + page copy constants
  lib/
    enter-app.ts                       # CREATE: enterApp(router) helper
  __tests__/
    dashboard.test.tsx                 # MODIFY: import path -> @/app/dashboard/page
    enterApp.test.ts                   # CREATE
    marketingPages.test.tsx            # CREATE
    marketingHome.test.tsx             # CREATE
```

Convention notes (match existing code):
- Path alias `@/*` maps to `apps/web/*`.
- Tests mock `next/navigation`, `@/lib/workspace`, `@/lib/api` (see `__tests__/dashboard.test.tsx`).
- Pages that touch `localStorage`/`useRouter` are `"use client"`.
- Tailwind v4 `dark:` variant already keys off `prefers-color-scheme` — no config needed.

---

## Task 1: Relocate the dashboard to `/dashboard`

**Files:**
- Create: `apps/web/app/dashboard/page.tsx` (moved content)
- Delete: `apps/web/app/page.tsx`
- Modify: `apps/web/app/trails/page.tsx:220`
- Modify: `apps/web/app/trails/[id]/page.tsx:137`, `:154`
- Modify: `apps/web/__tests__/dashboard.test.tsx` (import path)

- [ ] **Step 1: Move the page file (git mv preserves history)**

```bash
cd apps/web
mkdir -p app/dashboard
git mv app/page.tsx app/dashboard/page.tsx
```

The dashboard content is unchanged. It already routes to `/trails/new` and `/trails/<id>`, which still exist.

- [ ] **Step 2: Point the "home" links at `/dashboard`**

In `apps/web/app/trails/page.tsx`, change the header brand link (currently `href="/"`):

```tsx
          <Link
            href="/dashboard"
            className="text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            CoLearni
          </Link>
```

In `apps/web/app/trails/[id]/page.tsx`, both occurrences of `href="/"` (lines ~137 and ~154 — the brand/back-to-dashboard links) become `href="/dashboard"`. Leave every `href="/trails/..."` untouched.

- [ ] **Step 3: Fix the dashboard test import**

In `apps/web/__tests__/dashboard.test.tsx`, update `loadPage`:

```ts
async function loadPage() {
  const mod = await import("@/app/dashboard/page");
  return mod.default;
}
```

- [ ] **Step 4: Verify the moved dashboard test passes**

Run: `cd apps/web && npm run test -- dashboard`
Expected: PASS (same assertions, new path).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(web): move dashboard from / to /dashboard for marketing site

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add the Fraunces display font + marketing theme tokens

**Files:**
- Modify: `apps/web/app/layout.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: Register Fraunces in the root layout**

Edit `apps/web/app/layout.tsx`. Add the import and font, and expose its variable on `<html>`. Do NOT change the `<body>` classes (the product UI must stay light-only).

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono, Fraunces } from "next/font/google";
import "katex/dist/katex.min.css";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT", "WONK"],
});

export const metadata: Metadata = {
  title: "CoLearni",
  description: "Graph-first Socratic learning workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-slate-50 text-slate-950">{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Add marketing theme tokens + animation keyframes to `globals.css`**

Append to `apps/web/app/globals.css` (keep existing content). The `.marketing-surface` class scopes marketing colours so the product UI is untouched; dark values activate via `prefers-color-scheme`.

```css
/* ---- Phase 16.6 marketing surface ---- */
.font-display {
    font-family: var(--font-fraunces), Georgia, "Times New Roman", serif;
    font-optical-sizing: auto;
}

.marketing-surface {
    /* warm paper light theme */
    --mk-bg: #fbfaf7;
    --mk-bg-soft: #f3f1ea;
    --mk-fg: #0f172a;
    --mk-muted: #475569;
    --mk-border: #e6e2d8;
    --mk-card: #ffffff;
    --mk-accent: #2563eb;
    background-color: var(--mk-bg);
    color: var(--mk-fg);
}

@media (prefers-color-scheme: dark) {
    .marketing-surface {
        --mk-bg: #020617;
        --mk-bg-soft: #0b1222;
        --mk-fg: #e2e8f0;
        --mk-muted: #94a3b8;
        --mk-border: #1e293b;
        --mk-card: #0b1222;
        --mk-accent: #60a5fa;
        background-color: var(--mk-bg);
        color: var(--mk-fg);
    }
}

/* Grain overlay used by the marketing hero */
.mk-grain::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.4;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
    mix-blend-mode: overlay;
}

@keyframes mk-rise {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
}

.mk-reveal {
    opacity: 0;
}
.mk-reveal[data-shown="true"] {
    animation: mk-rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

@media (prefers-reduced-motion: reduce) {
    .mk-reveal,
    .mk-reveal[data-shown="true"] {
        opacity: 1;
        animation: none;
    }
}

@keyframes mk-node-pulse {
    0%, 100% { opacity: 0.55; }
    50% { opacity: 1; }
}

@keyframes mk-edge-draw {
    from { stroke-dashoffset: 1; }
    to { stroke-dashoffset: 0; }
}
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS (no errors).

- [ ] **Step 4: Commit**

```bash
git add app/layout.tsx app/globals.css
git commit -m "feat(web): add Fraunces display font + marketing theme tokens

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `enterApp` fake-login helper (TDD)

**Files:**
- Create: `apps/web/lib/enter-app.ts`
- Test: `apps/web/__tests__/enterApp.test.ts`

- [ ] **Step 1: Write the failing test**

Create `apps/web/__tests__/enterApp.test.ts`:

```ts
import { describe, expect, test, vi, beforeEach } from "vitest";

const ensureWorkspaceIdMock = vi.fn();

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: (...args: unknown[]) => ensureWorkspaceIdMock(...args),
}));

import { enterApp } from "@/lib/enter-app";

beforeEach(() => {
  ensureWorkspaceIdMock.mockReset();
});

describe("enterApp", () => {
  test("ensures a workspace then pushes to /dashboard", async () => {
    ensureWorkspaceIdMock.mockResolvedValue("ws-123");
    const push = vi.fn();

    await enterApp({ push });

    expect(ensureWorkspaceIdMock).toHaveBeenCalledTimes(1);
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  test("does not navigate if workspace creation fails", async () => {
    ensureWorkspaceIdMock.mockRejectedValue(new Error("offline"));
    const push = vi.fn();

    await expect(enterApp({ push })).rejects.toThrow("offline");
    expect(push).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- enterApp`
Expected: FAIL — cannot resolve `@/lib/enter-app`.

- [ ] **Step 3: Implement the helper**

Create `apps/web/lib/enter-app.ts`:

```ts
import { ensureWorkspaceId } from "@/lib/workspace";

/** Minimal slice of the Next.js router we depend on. */
export type AppRouterLike = {
  push: (href: string) => void;
};

/**
 * Fake-login entry point (Phase 16.6). Reuses the existing localStorage
 * workspace flow — no real auth. Creates the workspace on first use, then
 * routes into the product dashboard. Throws if the workspace cannot be
 * ensured, so callers can keep the user on the marketing page.
 */
export async function enterApp(router: AppRouterLike): Promise<void> {
  await ensureWorkspaceId();
  router.push("/dashboard");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- enterApp`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/enter-app.ts __tests__/enterApp.test.ts
git commit -m "feat(web): add enterApp fake-login helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Marketing content constants

**Files:**
- Create: `apps/web/components/marketing/marketing-content.ts`

- [ ] **Step 1: Create the content module**

Create `apps/web/components/marketing/marketing-content.ts`. Centralising nav + copy keeps pages declarative and tests stable.

```ts
export const NAV_LINKS = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/pedagogy", label: "Pedagogy" },
  { href: "/pricing", label: "Pricing" },
  { href: "/contact", label: "Contact" },
] as const;

export const CONTACT_EMAIL = "hello@colearni.app";
export const GITHUB_URL = "https://github.com/colearni";

export const HOW_IT_WORKS_STEPS = [
  {
    n: "01",
    title: "Name what you want to learn",
    body: "Describe a topic and a goal. CoLearni turns it into a Trail — a learning project scoped to where you are now.",
  },
  {
    n: "02",
    title: "A concept graph is built",
    body: "Your Trail becomes a prerequisite graph, from umbrella ideas down to granular concepts, so the order makes sense.",
  },
  {
    n: "03",
    title: "Click a concept, meet the tutor",
    body: "Open any concept and a Socratic tutor works with you — questions first, explanations when you need them.",
  },
  {
    n: "04",
    title: "Level up with a quiz",
    body: "When you are ready, a short level-up quiz checks real understanding instead of recognition.",
  },
  {
    n: "05",
    title: "Watch mastery update",
    body: "The graph colours in as you progress — mastered, learning, needs review — so you always know what is next.",
  },
] as const;

export const PEDAGOGY_SECTIONS = [
  {
    eyebrow: "The depth dial",
    title: "Bloom's Taxonomy as your target depth",
    body: "Every Trail has a target depth — from remembering and understanding up to analysing, evaluating, and creating. CoLearni aims its questions and quizzes at the level you chose, so “learn it” means the right thing for your goal.",
  },
  {
    eyebrow: "How the tutor talks",
    title: "Socratic questioning",
    body: "The tutor leads with questions that surface what you already believe, then nudges you to refine it. You do the thinking; it provides the scaffolding and steps in with direct explanation only when you are genuinely stuck.",
  },
  {
    eyebrow: "Don't move on too early",
    title: "Bloom mastery learning",
    body: "Concepts are gated by mastery, not by time spent. You advance when you can actually use an idea — and the system routes you back to weak spots before they compound.",
  },
  {
    eyebrow: "Make it stick",
    title: "Active recall & retrieval practice",
    body: "Level-up quizzes ask you to retrieve and apply, not just recognise. Pulling knowledge out strengthens it far more than reading it again.",
  },
  {
    eyebrow: "Build on firm ground",
    title: "Scaffolding along a prerequisite graph",
    body: "New concepts are introduced only once their prerequisites are in place. The graph keeps you on solid footing instead of dropping you into the deep end.",
  },
] as const;

export const PRICING_TIERS = [
  {
    name: "Self-host / Open source",
    pitch: "Run CoLearni on your own machine or server. Bring your own LLM key.",
    points: ["Local-first", "Your data stays yours", "Source-available"],
  },
  {
    name: "Free hosted",
    pitch: "A hosted tier so you can start learning without setting anything up.",
    points: ["Nothing to install", "Core learning loop", "Limits TBC"],
  },
  {
    name: "Paid hosted",
    pitch: "More capacity and hosted conveniences for serious, ongoing learning.",
    points: ["Higher limits", "Hosted LLM keys", "Pricing TBC"],
  },
] as const;
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add components/marketing/marketing-content.ts
git commit -m "feat(web): add marketing content constants

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `SectionReveal` scroll-reveal wrapper

**Files:**
- Create: `apps/web/components/marketing/SectionReveal.tsx`

- [ ] **Step 1: Implement the component**

Create `apps/web/components/marketing/SectionReveal.tsx`. It adds `data-shown="true"` when scrolled into view; the CSS (`.mk-reveal`) handles the animation and respects reduced-motion. Falls back to shown if `IntersectionObserver` is unavailable (e.g. jsdom).

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

export function SectionReveal({
  children,
  className = "",
  delayMs = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`mk-reveal ${className}`}
      data-shown={shown ? "true" : "false"}
      style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add components/marketing/SectionReveal.tsx
git commit -m "feat(web): add SectionReveal scroll-reveal wrapper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `EnterAppButton` + `RedirectGate`

**Files:**
- Create: `apps/web/components/marketing/EnterAppButton.tsx`
- Create: `apps/web/components/marketing/RedirectGate.tsx`

- [ ] **Step 1: Implement `EnterAppButton`**

Create `apps/web/components/marketing/EnterAppButton.tsx`. Shared fake-login CTA with pending + error state.

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { enterApp } from "@/lib/enter-app";

export function EnterAppButton({
  children = "Log in",
  className = "",
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function handleClick() {
    setPending(true);
    setError(false);
    try {
      await enterApp(router);
    } catch {
      setError(true);
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      className={className}
    >
      {pending ? "Opening…" : error ? "Try again" : children}
    </button>
  );
}
```

- [ ] **Step 2: Implement `RedirectGate`**

Create `apps/web/components/marketing/RedirectGate.tsx`. On `/`, returning users (workspace already in localStorage) are sent to `/dashboard`. Renders nothing.

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { WORKSPACE_STORAGE_KEY } from "@/lib/workspace";

export function RedirectGate() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (existing) {
      router.replace("/dashboard");
    }
  }, [router]);

  return null;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS (`WORKSPACE_STORAGE_KEY` is exported from `lib/workspace.ts`).

- [ ] **Step 4: Commit**

```bash
git add components/marketing/EnterAppButton.tsx components/marketing/RedirectGate.tsx
git commit -m "feat(web): add EnterAppButton + RedirectGate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Marketing nav + footer

**Files:**
- Create: `apps/web/components/marketing/MarketingNav.tsx`
- Create: `apps/web/components/marketing/MarketingFooter.tsx`

- [ ] **Step 1: Implement `MarketingNav`**

Create `apps/web/components/marketing/MarketingNav.tsx`.

```tsx
import Link from "next/link";

import { NAV_LINKS } from "@/components/marketing/marketing-content";
import { EnterAppButton } from "@/components/marketing/EnterAppButton";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--mk-border)] bg-[var(--mk-bg)]/80 backdrop-blur">
      <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link
          href="/"
          className="font-display text-xl font-semibold tracking-tight text-[var(--mk-fg)]"
        >
          CoLearni
        </Link>
        <div className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-[var(--mk-muted)] transition-colors hover:text-[var(--mk-fg)]"
            >
              {link.label}
            </Link>
          ))}
        </div>
        <EnterAppButton className="inline-flex h-9 items-center justify-center rounded-full bg-[var(--mk-accent)] px-4 text-sm font-semibold text-white transition-transform hover:scale-[1.03] disabled:opacity-60">
          Log in
        </EnterAppButton>
      </nav>
    </header>
  );
}
```

- [ ] **Step 2: Implement `MarketingFooter`**

Create `apps/web/components/marketing/MarketingFooter.tsx`.

```tsx
import Link from "next/link";

import {
  CONTACT_EMAIL,
  GITHUB_URL,
  NAV_LINKS,
} from "@/components/marketing/marketing-content";

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--mk-border)] bg-[var(--mk-bg-soft)]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 py-12 sm:px-8 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <p className="font-display text-lg font-semibold text-[var(--mk-fg)]">
            CoLearni
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
            A personal learning workspace: a concept graph, a Socratic tutor, and
            mastery you can see.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-10 gap-y-3">
          <nav className="flex flex-col gap-2">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <nav className="flex flex-col gap-2">
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={GITHUB_URL}
              className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
            >
              GitHub
            </a>
          </nav>
        </div>
      </div>
      <div className="border-t border-[var(--mk-border)] px-5 py-5 text-center text-xs text-[var(--mk-muted)] sm:px-8">
        © {new Date().getFullYear()} CoLearni · Source-available, license to be
        announced
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add components/marketing/MarketingNav.tsx components/marketing/MarketingFooter.tsx
git commit -m "feat(web): add marketing nav and footer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Marketing layout (themed wrapper)

**Files:**
- Create: `apps/web/app/(marketing)/layout.tsx`

- [ ] **Step 1: Implement the layout**

Create `apps/web/app/(marketing)/layout.tsx`. Full-bleed `.marketing-surface` wrapper so the product's `bg-slate-50` body never shows through in dark mode. Uses Geist body via the root `<html>` font variables; headings opt into `.font-display`.

```tsx
import { MarketingNav } from "@/components/marketing/MarketingNav";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="marketing-surface flex min-h-screen flex-col font-[family-name:var(--font-geist-sans)]">
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/layout.tsx"
git commit -m "feat(web): add marketing route-group layout

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: `GraphHero` motif

**Files:**
- Create: `apps/web/components/marketing/GraphHero.tsx`

- [ ] **Step 1: Implement the animated concept-graph SVG**

Create `apps/web/components/marketing/GraphHero.tsx`. Pure SVG/CSS — no deps. Nodes use the mastery spectrum (emerald/blue/amber/slate); edges draw in; nodes pulse. Decorative, so `aria-hidden`.

```tsx
const NODES = [
  { id: "a", x: 60, y: 150, r: 13, c: "#10b981" },
  { id: "b", x: 150, y: 70, r: 11, c: "#10b981" },
  { id: "c", x: 165, y: 220, r: 11, c: "#2563eb" },
  { id: "d", x: 270, y: 130, r: 15, c: "#2563eb" },
  { id: "e", x: 300, y: 250, r: 10, c: "#f59e0b" },
  { id: "f", x: 390, y: 80, r: 10, c: "#94a3b8" },
  { id: "g", x: 410, y: 200, r: 12, c: "#94a3b8" },
];

const EDGES: Array<[string, string]> = [
  ["a", "b"],
  ["a", "c"],
  ["b", "d"],
  ["c", "d"],
  ["c", "e"],
  ["d", "f"],
  ["d", "g"],
  ["e", "g"],
];

function node(id: string) {
  const n = NODES.find((x) => x.id === id);
  if (!n) throw new Error(`unknown node ${id}`);
  return n;
}

export function GraphHero({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 470 300"
      className={className}
      role="img"
      aria-label="A concept graph lighting up from mastered to new"
    >
      <g stroke="currentColor" strokeWidth="1.5" opacity="0.35">
        {EDGES.map(([from, to], i) => {
          const a = node(from);
          const b = node(to);
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              pathLength={1}
              strokeDasharray="1"
              style={{
                animation: `mk-edge-draw 0.9s ease forwards`,
                animationDelay: `${0.15 * i}s`,
                strokeDashoffset: 1,
              }}
            />
          );
        })}
      </g>
      {NODES.map((n, i) => (
        <circle
          key={n.id}
          cx={n.x}
          cy={n.y}
          r={n.r}
          fill={n.c}
          style={{
            animation: `mk-node-pulse 3.2s ease-in-out infinite`,
            animationDelay: `${0.2 * i}s`,
          }}
        />
      ))}
    </svg>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add components/marketing/GraphHero.tsx
git commit -m "feat(web): add animated GraphHero concept-graph motif

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: `ProductPreview` (in-CSS faux product shot)

**Files:**
- Create: `apps/web/components/marketing/ProductPreview.tsx`

- [ ] **Step 1: Implement the preview**

Create `apps/web/components/marketing/ProductPreview.tsx`. A stylised mock of the product: a mini graph beside a faux Socratic tutor exchange. Built, not a screenshot. Decorative.

```tsx
import { GraphHero } from "@/components/marketing/GraphHero";

export function ProductPreview({ className = "" }: { className?: string }) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-[var(--mk-border)] bg-[var(--mk-card)] shadow-xl ${className}`}
      aria-hidden="true"
    >
      <div className="flex items-center gap-1.5 border-b border-[var(--mk-border)] px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400" />
        <span className="h-3 w-3 rounded-full bg-amber-400" />
        <span className="h-3 w-3 rounded-full bg-emerald-400" />
        <span className="ml-3 text-xs font-medium text-[var(--mk-muted)]">
          Trail · Linear Algebra
        </span>
      </div>
      <div className="grid gap-0 md:grid-cols-2">
        <div className="border-b border-[var(--mk-border)] p-5 text-[var(--mk-accent)] md:border-b-0 md:border-r">
          <GraphHero className="h-44 w-full" />
        </div>
        <div className="flex flex-col gap-3 p-5">
          <div className="self-start rounded-2xl rounded-tl-sm bg-[var(--mk-bg-soft)] px-3 py-2 text-sm text-[var(--mk-fg)]">
            What happens to a vector when you multiply it by this matrix?
          </div>
          <div className="self-end rounded-2xl rounded-tr-sm bg-[var(--mk-accent)] px-3 py-2 text-sm text-white">
            It gets scaled and rotated?
          </div>
          <div className="self-start rounded-2xl rounded-tl-sm bg-[var(--mk-bg-soft)] px-3 py-2 text-sm text-[var(--mk-fg)]">
            Close. Which part of the matrix controls the rotation — can you
            point to it?
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              Learning → Mastered
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add components/marketing/ProductPreview.tsx
git commit -m "feat(web): add in-CSS ProductPreview shot

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Home page (`/`)

**Files:**
- Create: `apps/web/app/(marketing)/page.tsx`

- [ ] **Step 1: Implement the Home page**

Create `apps/web/app/(marketing)/page.tsx`. `"use client"` because of `RedirectGate`/`EnterAppButton`. Hero with graph motif + centered primary CTA, product preview, how-it-works strip, pedagogy teaser, footer CTA.

```tsx
"use client";

import Link from "next/link";

import { RedirectGate } from "@/components/marketing/RedirectGate";
import { EnterAppButton } from "@/components/marketing/EnterAppButton";
import { GraphHero } from "@/components/marketing/GraphHero";
import { ProductPreview } from "@/components/marketing/ProductPreview";
import { SectionReveal } from "@/components/marketing/SectionReveal";
import { HOW_IT_WORKS_STEPS } from "@/components/marketing/marketing-content";

export default function MarketingHome() {
  return (
    <>
      <RedirectGate />

      {/* Hero */}
      <section className="relative mk-grain overflow-hidden">
        <div
          className="pointer-events-none absolute -top-24 left-1/2 h-[420px] w-[820px] -translate-x-1/2 rounded-full opacity-30 blur-3xl"
          style={{
            background:
              "radial-gradient(closest-side, var(--mk-accent), transparent)",
          }}
          aria-hidden="true"
        />
        <div className="mx-auto grid w-full max-w-6xl items-center gap-12 px-5 py-20 sm:px-8 md:grid-cols-2 md:py-28">
          <div>
            <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
              Graph-first Socratic learning
            </p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-[var(--mk-fg)] sm:text-6xl">
              Learn anything as a graph, with a tutor that meets you where you
              are.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-7 text-[var(--mk-muted)]">
              CoLearni turns a goal into a concept graph, then coaches you
              through it one idea at a time — Socratic questions, real
              mastery, no busywork.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <EnterAppButton className="inline-flex h-12 items-center justify-center rounded-full bg-[var(--mk-accent)] px-7 text-base font-semibold text-white shadow-lg shadow-blue-500/20 transition-transform hover:scale-[1.03] disabled:opacity-60">
                Start learning free
              </EnterAppButton>
              <Link
                href="/how-it-works"
                className="inline-flex h-12 items-center justify-center rounded-full border border-[var(--mk-border)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg-soft)]"
              >
                See how it works
              </Link>
            </div>
          </div>
          <div className="text-[var(--mk-accent)]">
            <GraphHero className="h-72 w-full" />
          </div>
        </div>
      </section>

      {/* Product preview */}
      <section className="mx-auto w-full max-w-5xl px-5 pb-8 sm:px-8">
        <SectionReveal>
          <ProductPreview />
        </SectionReveal>
      </section>

      {/* How it works strip */}
      <section className="mx-auto w-full max-w-6xl px-5 py-20 sm:px-8">
        <SectionReveal>
          <h2 className="font-display text-3xl font-semibold tracking-tight text-[var(--mk-fg)]">
            From a goal to mastery, in five moves
          </h2>
        </SectionReveal>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {HOW_IT_WORKS_STEPS.map((step, i) => (
            <SectionReveal key={step.n} delayMs={i * 80}>
              <div className="h-full rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5">
                <p className="font-[family-name:var(--font-geist-mono)] text-sm text-[var(--mk-accent)]">
                  {step.n}
                </p>
                <h3 className="mt-3 font-display text-lg font-semibold text-[var(--mk-fg)]">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
                  {step.body}
                </p>
              </div>
            </SectionReveal>
          ))}
        </div>
      </section>

      {/* Pedagogy teaser */}
      <section className="bg-[var(--mk-bg-soft)]">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-6 px-5 py-20 sm:px-8 md:flex-row md:items-center md:justify-between">
          <SectionReveal>
            <div className="max-w-xl">
              <h2 className="font-display text-3xl font-semibold tracking-tight text-[var(--mk-fg)]">
                Built on how people actually learn
              </h2>
              <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
                Bloom&apos;s Taxonomy sets your target depth. Socratic
                questioning, mastery gating, retrieval practice, and prerequisite
                scaffolding do the rest.
              </p>
            </div>
          </SectionReveal>
          <Link
            href="/pedagogy"
            className="inline-flex h-11 shrink-0 items-center justify-center rounded-full border border-[var(--mk-border)] bg-[var(--mk-card)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg)]"
          >
            Read the pedagogy
          </Link>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="mx-auto w-full max-w-4xl px-5 py-24 text-center sm:px-8">
        <SectionReveal>
          <h2 className="font-display text-4xl font-semibold tracking-tight text-[var(--mk-fg)]">
            Pick something you&apos;ve always wanted to understand.
          </h2>
          <p className="mt-4 text-lg text-[var(--mk-muted)]">
            Start a Trail in under a minute. No account required to try it.
          </p>
          <div className="mt-8 flex justify-center">
            <EnterAppButton className="inline-flex h-12 items-center justify-center rounded-full bg-[var(--mk-accent)] px-8 text-base font-semibold text-white shadow-lg shadow-blue-500/20 transition-transform hover:scale-[1.03] disabled:opacity-60">
              Start learning free
            </EnterAppButton>
          </div>
        </SectionReveal>
      </section>
    </>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/page.tsx"
git commit -m "feat(web): add marketing Home page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 12: How it works page (`/how-it-works`)

**Files:**
- Create: `apps/web/app/(marketing)/how-it-works/page.tsx`

- [ ] **Step 1: Implement the page**

Create `apps/web/app/(marketing)/how-it-works/page.tsx`. Server component (no client hooks). Numbered demo loop + a placeholder media frame.

```tsx
import type { Metadata } from "next";
import Link from "next/link";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { ProductPreview } from "@/components/marketing/ProductPreview";
import { HOW_IT_WORKS_STEPS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "How it works · CoLearni",
  description: "From a goal to mastery: how CoLearni teaches.",
};

export default function HowItWorksPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          How it works
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          One loop, repeated until it sticks.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          CoLearni runs the same tight loop for every concept in your Trail. Each
          pass moves you from recognising an idea to genuinely using it.
        </p>
      </header>

      <SectionReveal className="mt-12">
        <ProductPreview />
      </SectionReveal>

      <ol className="mt-16 flex flex-col gap-5">
        {HOW_IT_WORKS_STEPS.map((step, i) => (
          <SectionReveal key={step.n} delayMs={i * 60}>
            <li className="flex gap-5 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-6">
              <span className="font-display text-3xl font-semibold text-[var(--mk-accent)]">
                {step.n}
              </span>
              <div>
                <h2 className="font-display text-xl font-semibold text-[var(--mk-fg)]">
                  {step.title}
                </h2>
                <p className="mt-2 text-base leading-7 text-[var(--mk-muted)]">
                  {step.body}
                </p>
              </div>
            </li>
          </SectionReveal>
        ))}
      </ol>

      <div className="mt-16 flex justify-center">
        <Link
          href="/pedagogy"
          className="inline-flex h-11 items-center justify-center rounded-full border border-[var(--mk-border)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg-soft)]"
        >
          Why this works →
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/how-it-works/page.tsx"
git commit -m "feat(web): add How it works page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 13: Pedagogy page (`/pedagogy`)

**Files:**
- Create: `apps/web/app/(marketing)/pedagogy/page.tsx`

- [ ] **Step 1: Implement the page**

Create `apps/web/app/(marketing)/pedagogy/page.tsx`. Server component. One section per pedagogy principle (from constants), alternating layout.

```tsx
import type { Metadata } from "next";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { PEDAGOGY_SECTIONS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Pedagogy · CoLearni",
  description:
    "Bloom's Taxonomy, Socratic questioning, mastery learning, retrieval practice, and prerequisite scaffolding.",
};

export default function PedagogyPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Pedagogy
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          A coach, not a search engine.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          CoLearni is built on established learning science. Here is what is
          actually happening while you learn.
        </p>
      </header>

      <div className="mt-14 flex flex-col gap-12">
        {PEDAGOGY_SECTIONS.map((section, i) => (
          <SectionReveal key={section.title} delayMs={i * 60}>
            <section className="border-l-2 border-[var(--mk-accent)] pl-6">
              <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.18em] text-[var(--mk-accent)]">
                {section.eyebrow}
              </p>
              <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-[var(--mk-fg)]">
                {section.title}
              </h2>
              <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
                {section.body}
              </p>
            </section>
          </SectionReveal>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/pedagogy/page.tsx"
git commit -m "feat(web): add Pedagogy page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 14: Pricing page (`/pricing`, TBC)

**Files:**
- Create: `apps/web/app/(marketing)/pricing/page.tsx`

- [ ] **Step 1: Implement the page**

Create `apps/web/app/(marketing)/pricing/page.tsx`. Server component. Three tiers, each stamped **TBC**, no numbers. License note: source-available, not MIT, no specific license named.

```tsx
import type { Metadata } from "next";
import { Check } from "lucide-react";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { PRICING_TIERS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Pricing · CoLearni",
  description: "Anticipated tiers. Pricing is still to be confirmed.",
};

export default function PricingPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Pricing
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          Pricing is still being worked out.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Here is the shape we are planning. Nothing below is final — every
          tier is marked TBC, and the line between free and self-host is not
          settled yet.
        </p>
      </header>

      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {PRICING_TIERS.map((tier, i) => (
          <SectionReveal key={tier.name} delayMs={i * 80}>
            <div className="flex h-full flex-col rounded-2xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-6">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold text-[var(--mk-fg)]">
                  {tier.name}
                </h2>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  TBC
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-[var(--mk-muted)]">
                {tier.pitch}
              </p>
              <ul className="mt-5 flex flex-col gap-2">
                {tier.points.map((point) => (
                  <li
                    key={point}
                    className="flex items-center gap-2 text-sm text-[var(--mk-fg)]"
                  >
                    <Check
                      className="h-4 w-4 shrink-0 text-[var(--mk-accent)]"
                      aria-hidden="true"
                    />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          </SectionReveal>
        ))}
      </div>

      <SectionReveal className="mt-12">
        <div className="rounded-xl border border-[var(--mk-border)] bg-[var(--mk-bg-soft)] p-6">
          <h2 className="font-display text-lg font-semibold text-[var(--mk-fg)]">
            On licensing
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
            CoLearni is intended to be source-available, with a commercial head
            start for the hosted service. It is deliberately not MIT-licensed.
            The exact license has not been chosen yet, so we are not committing
            to specific terms here.
          </p>
        </div>
      </SectionReveal>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS (`Check` is exported by `lucide-react`, already a dependency).

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/pricing/page.tsx"
git commit -m "feat(web): add Pricing (TBC) page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 15: Contact page (`/contact`, info card)

**Files:**
- Create: `apps/web/app/(marketing)/contact/page.tsx`

- [ ] **Step 1: Implement the page**

Create `apps/web/app/(marketing)/contact/page.tsx`. Server component. Info card only — email + GitHub. No form, no backend.

```tsx
import type { Metadata } from "next";
import { Mail, Github } from "lucide-react";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import {
  CONTACT_EMAIL,
  GITHUB_URL,
} from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Contact · CoLearni",
  description: "Get in touch with the CoLearni team.",
};

export default function ContactPage() {
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-16 sm:px-8 md:py-28">
      <header>
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Contact
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          We&apos;d love to hear from you.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Questions, ideas, or feedback about CoLearni? Reach out directly —
          a real person reads every message.
        </p>
      </header>

      <SectionReveal className="mt-10">
        <div className="flex flex-col gap-4">
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="flex items-center gap-4 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5 transition-colors hover:bg-[var(--mk-bg-soft)]"
          >
            <Mail className="h-5 w-5 text-[var(--mk-accent)]" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-[var(--mk-fg)]">Email</p>
              <p className="text-sm text-[var(--mk-muted)]">{CONTACT_EMAIL}</p>
            </div>
          </a>
          <a
            href={GITHUB_URL}
            className="flex items-center gap-4 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5 transition-colors hover:bg-[var(--mk-bg-soft)]"
          >
            <Github
              className="h-5 w-5 text-[var(--mk-accent)]"
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-semibold text-[var(--mk-fg)]">GitHub</p>
              <p className="text-sm text-[var(--mk-muted)]">
                Follow development and open issues
              </p>
            </div>
          </a>
        </div>
      </SectionReveal>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npm run typecheck`
Expected: PASS (`Mail`, `Github` exported by `lucide-react`).

- [ ] **Step 3: Commit**

```bash
git add "app/(marketing)/contact/page.tsx"
git commit -m "feat(web): add Contact page (info card)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 16: Marketing page render tests (TDD-style coverage)

**Files:**
- Create: `apps/web/__tests__/marketingPages.test.tsx`

- [ ] **Step 1: Write the tests**

Create `apps/web/__tests__/marketingPages.test.tsx`. Covers: every route renders its key heading with no workspace; pages render under a dark `matchMedia` mock; the marketing wrapper is present. Mocks `next/navigation` (for the Home page's client hooks).

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/workspace", () => ({
  WORKSPACE_STORAGE_KEY: "colearni_workspace_id",
  ensureWorkspaceId: vi.fn().mockResolvedValue("ws-1"),
}));

import MarketingLayout from "@/app/(marketing)/layout";
import HowItWorksPage from "@/app/(marketing)/how-it-works/page";
import PedagogyPage from "@/app/(marketing)/pedagogy/page";
import PricingPage from "@/app/(marketing)/pricing/page";
import ContactPage from "@/app/(marketing)/contact/page";

beforeEach(() => {
  window.localStorage.clear();
});

describe("marketing pages render without a workspace", () => {
  test("How it works", () => {
    render(<HowItWorksPage />);
    expect(
      screen.getByRole("heading", { name: /one loop, repeated/i }),
    ).toBeInTheDocument();
  });

  test("Pedagogy mentions Bloom's Taxonomy", () => {
    render(<PedagogyPage />);
    expect(screen.getByText(/Bloom's Taxonomy/i)).toBeInTheDocument();
  });

  test("Pricing marks every tier TBC and avoids numbers", () => {
    render(<PricingPage />);
    expect(screen.getAllByText(/TBC/).length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(/not MIT-licensed/i)).toBeInTheDocument();
  });

  test("Contact shows an email, no form", () => {
    const { container } = render(<ContactPage />);
    expect(screen.getByText(/hello@colearni\.app/i)).toBeInTheDocument();
    expect(container.querySelector("form")).toBeNull();
  });
});

describe("marketing layout + theming", () => {
  test("wraps children in the themed marketing surface", () => {
    const { container } = render(
      <MarketingLayout>
        <p>hello</p>
      </MarketingLayout>,
    );
    expect(container.querySelector(".marketing-surface")).not.toBeNull();
  });

  test("pages render under a dark prefers-color-scheme", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("dark"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    expect(() => render(<PedagogyPage />)).not.toThrow();
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd apps/web && npm run test -- marketingPages`
Expected: PASS (all tests).

- [ ] **Step 3: Commit**

```bash
git add __tests__/marketingPages.test.tsx
git commit -m "test(web): marketing pages render + theming coverage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 17: Home redirect + fake-login navigation tests

**Files:**
- Create: `apps/web/__tests__/marketingHome.test.tsx`

- [ ] **Step 1: Write the tests**

Create `apps/web/__tests__/marketingHome.test.tsx`. Covers: returning users (workspace present) are redirected from `/` to `/dashboard`; first-time visitors see the hero; clicking "Start learning free" ensures a workspace and pushes to `/dashboard`.

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

const pushMock = vi.fn();
const replaceMock = vi.fn();
const ensureWorkspaceIdMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}));

vi.mock("@/lib/workspace", () => ({
  WORKSPACE_STORAGE_KEY: "colearni_workspace_id",
  ensureWorkspaceId: (...args: unknown[]) => ensureWorkspaceIdMock(...args),
}));

import MarketingHome from "@/app/(marketing)/page";

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
  ensureWorkspaceIdMock.mockReset();
  ensureWorkspaceIdMock.mockResolvedValue("ws-1");
  window.localStorage.clear();
});

describe("marketing Home", () => {
  test("redirects returning users with a workspace to /dashboard", async () => {
    window.localStorage.setItem("colearni_workspace_id", "ws-existing");
    render(<MarketingHome />);
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  test("first-time visitor sees the hero, no redirect", () => {
    render(<MarketingHome />);
    expect(
      screen.getByRole("heading", { name: /learn anything as a graph/i }),
    ).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  test("Start learning free ensures workspace and enters the app", async () => {
    const user = userEvent.setup();
    render(<MarketingHome />);
    const [cta] = screen.getAllByRole("button", {
      name: /start learning free/i,
    });
    await user.click(cta);
    await waitFor(() => {
      expect(ensureWorkspaceIdMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd apps/web && npm run test -- marketingHome`
Expected: PASS (3 tests).

- [ ] **Step 3: Commit**

```bash
git add __tests__/marketingHome.test.tsx
git commit -m "test(web): marketing Home redirect + fake-login navigation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 18: Full verification

- [ ] **Step 1: Typecheck the whole frontend**

Run: `cd apps/web && npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd apps/web && npm run test`
Expected: PASS — all existing suites plus `enterApp`, `marketingPages`, `marketingHome`, and the relocated `dashboard` test.

- [ ] **Step 3: Lint**

Run: `cd apps/web && npm run lint`
Expected: PASS (no new errors).

- [ ] **Step 4: Manual smoke (dev server)**

Run: `cd apps/web && npm run dev`, then visit:
- `/` — marketing Home (graph hero, CTA). With a `colearni_workspace_id` in localStorage, it redirects to `/dashboard`.
- `/how-it-works`, `/pedagogy`, `/pricing`, `/contact` — render with nav + footer.
- Click **Log in** / **Start learning free** — lands on `/dashboard`.
- Toggle OS dark mode — marketing surface flips light/dark; product pages unaffected.

- [ ] **Step 5: Update the rebuild plan checklist (if present)**

If `docs/REBUILD_PLAN.md` tracks per-phase completion, mark Phase 16.6 PR-sized items done. Otherwise skip.

- [ ] **Step 6: Final commit (only if Step 5 changed files)**

```bash
git add docs/REBUILD_PLAN.md
git commit -m "docs: mark Phase 16.6 marketing site complete

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Marketing routes (Home/How it works/Pedagogy/Pricing/Contact) → Tasks 11–15. ✓
- Pedagogy real teaching story (Bloom depth dial, Socratic, mastery, retrieval, scaffolding) → Task 4 constants + Task 13. ✓
- Fake login in top-right header + centered Home CTA, reuses localStorage workspace id → Tasks 3, 6, 7, 11. ✓
- Pricing TBC tiers (self-host/free/paid) + license note (not MIT, unnamed) → Task 14. ✓
- Demos as screenshots/GIFs later; in-CSS preview now → Task 10. ✓
- Public, workspace-free pages → Task 16 (renders with cleared localStorage). ✓
- Fake login no real credentials/secrets → Task 3 (only `ensureWorkspaceId`). ✓
- Consistent theming incl. dark mode → Tasks 2, 8, 16. ✓
- Routing: marketing at `/`, redirect by workspace, dashboard → `/dashboard` → Tasks 1, 6, 11, 17. ✓
- Tests: render without workspace; fake login navigates; light + dark → Tasks 16, 17. ✓

**Placeholder scan:** No TBD/TODO in code (the visible "TBC" is required product copy). All steps include complete code.

**Type consistency:** `enterApp(router)` takes `AppRouterLike { push }` (Task 3) and is called with the real router (Task 6). `WORKSPACE_STORAGE_KEY` imported from `lib/workspace.ts` (exists). `SectionReveal` props (`children`, `className`, `delayMs`) consistent across Tasks 5, 11–15. `GraphHero`/`ProductPreview` `className` prop consistent. Content constant names (`HOW_IT_WORKS_STEPS`, `PEDAGOGY_SECTIONS`, `PRICING_TIERS`, `NAV_LINKS`, `CONTACT_EMAIL`, `GITHUB_URL`) consistent across Task 4 and consumers.
